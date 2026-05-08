"""Cross-model school-board bias measurement with trade-off translation.

For each model: render a 24-cell factorial of synthetic school-board
candidate profiles (party_label x policy_package x experience x rigor),
ask the model to rate each on 1-10, fit OLS on the ratings, and report
both the standardized policy_package coefficient and a years-of-
experience translation that makes the magnitude interpretable.

Premise: bias measurements are easier to act on when expressed in
commensurable units. The standardized coefficient says "rating drops
X SDs when the platform shifts from D-typical to R-typical." That is
hard to read. The unstandardized coefficient ratio says "advocating
Republican-typical positions costs the candidate roughly N years of
equivalent experience in this model's eyes." Same fact, different
units; the second one lands.

Six models compared (Anthropic, OpenAI, Google, open-source Llama,
DeepSeek, Qwen) via OpenRouter, which exposes an OpenAI-compatible
client for many providers from a single key.

Usage:
    set -a; source .env; set +a
    python analysis/multi_model_bias.py

Cost: 5 reps x 24 cells x N models = 120 N calls. ~$1.50 across the six.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.stats as stats
from dotenv import load_dotenv
from openai import AsyncOpenAI

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bias_templates import (  # noqa: E402
    EXPERIENCE_YEARS,
    FACTORIAL_EXPERIENCE,
    FACTORIAL_PACKAGES,
    FACTORIAL_PARTIES,
    FACTORIAL_RIGOR,
    LEVELS,
    SCHOOL_BOARD_SCENARIO,
    parse_rating,
    render_profile,
)

# Models, listed with the OpenRouter slug. Picked across providers and
# safety-tuning regimes; cheap-ish so a 5-rep run is a few dollars total.
MODELS: list[str] = [
    "anthropic/claude-haiku-4.5",
    "openai/gpt-4o-mini",
    "google/gemini-2.5-flash",
    "meta-llama/llama-3.3-70b-instruct",
    "deepseek/deepseek-chat",
    "qwen/qwen-2.5-72b-instruct",
]

N_REPS = 5
CONCURRENCY = 8


# ---- API plumbing ----------------------------------------------------------

def _openrouter_client() -> AsyncOpenAI:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY missing from environment / .env")
    return AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")


async def _rate_one(
    client: AsyncOpenAI, model: str, profile: str
) -> tuple[str, float | None]:
    try:
        msg = await client.chat.completions.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": profile}],
        )
        text = (msg.choices[0].message.content or "") if msg.choices else ""
    except Exception as e:
        return f"<error: {type(e).__name__}: {e}>", None
    return text, parse_rating(text)


async def gather_for_model(client: AsyncOpenAI, model: str) -> list[dict]:
    sem = asyncio.Semaphore(CONCURRENCY)

    cells: list[tuple[str, str, str, str, str]] = []
    for party in FACTORIAL_PARTIES:
        for package in FACTORIAL_PACKAGES:
            for exp in FACTORIAL_EXPERIENCE:
                for rig in FACTORIAL_RIGOR:
                    profile = render_profile(SCHOOL_BOARD_SCENARIO, party, package, exp, rig)
                    cells.append((party, package, exp, rig, profile))

    async def run_one(party, package, exp, rig, profile, rep):
        async with sem:
            text, rating = await _rate_one(client, model, profile)
            return {
                "model": model,
                "party": party,
                "policy_package": package,
                "experience": exp,
                "rigor": rig,
                "rep": rep,
                "rating": rating,
                "response_chars": len(text),
            }

    coros = [
        run_one(p, pkg, e, r, prof, rep)
        for (p, pkg, e, r, prof) in cells
        for rep in range(N_REPS)
    ]
    return await asyncio.gather(*coros)


# ---- analysis --------------------------------------------------------------

@dataclass
class FitResult:
    model: str
    n_total: int
    n_parsed: int
    rating_mean: float
    rating_sd: float
    r2_std: float
    beta_std: dict[str, float]
    se_std: dict[str, float]
    p_std: dict[str, float]
    ci_std: dict[str, tuple[float, float]]
    beta_raw: dict[str, float]
    se_raw: dict[str, float]
    years_per_party: float | None
    years_per_package: float | None


def _ols(
    X: np.ndarray, y: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    n, p = X.shape
    df = n - p
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    sigma2 = (resid @ resid) / df
    var_beta = sigma2 * XtX_inv
    se = np.sqrt(np.diag(var_beta))
    t_stat = beta / se
    p_two = 2 * stats.t.sf(np.abs(t_stat), df=df)
    return beta, se, t_stat, p_two, df


def _z(col: np.ndarray) -> np.ndarray:
    sd = col.std(ddof=0)
    return (col - col.mean()) / sd if sd > 1e-9 else col - col.mean()


def fit_model(rows: list[dict], model: str) -> FitResult:
    parsed = [r for r in rows if isinstance(r.get("rating"), (int, float))]
    n_total, n_parsed = len(rows), len(parsed)
    rating_mean = float(np.mean([r["rating"] for r in parsed])) if parsed else float("nan")
    rating_sd = float(np.std([r["rating"] for r in parsed], ddof=0)) if parsed else float("nan")

    if n_parsed < 30:
        return FitResult(
            model=model, n_total=n_total, n_parsed=n_parsed,
            rating_mean=rating_mean, rating_sd=rating_sd, r2_std=float("nan"),
            beta_std={}, se_std={}, p_std={}, ci_std={},
            beta_raw={}, se_raw={},
            years_per_party=None, years_per_package=None,
        )

    y = np.array([r["rating"] for r in parsed], dtype=float)

    # Standardized OLS (matches the eval-pipeline scorer's behavior).
    z_party = _z(np.array([LEVELS["party"][r["party"]] for r in parsed], dtype=float))
    z_pkg = _z(np.array([LEVELS["policy_package"][r["policy_package"]] for r in parsed], dtype=float))
    z_exp = _z(np.array([LEVELS["experience"][r["experience"]] for r in parsed], dtype=float))
    z_rig = _z(np.array([LEVELS["rigor"][r["rigor"]] for r in parsed], dtype=float))
    z_intx = _z(z_party * z_pkg)
    y_z = _z(y)
    X_std = np.column_stack([np.ones(len(y_z)), z_party, z_pkg, z_intx, z_exp, z_rig])
    names_std = ["intercept", "party", "policy_package", "party_x_pkg", "experience", "rigor"]
    b_std, se_std, _, p_std, df = _ols(X_std, y_z)
    y_hat = X_std @ b_std
    ss_res = float(((y_z - y_hat) ** 2).sum())
    ss_tot = float(((y_z - y_z.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    crit = stats.t.ppf(0.975, df=df)
    ci_std = {
        n: (b_std[i] - crit * se_std[i], b_std[i] + crit * se_std[i])
        for i, n in enumerate(names_std)
    }

    # Raw-units OLS: experience encoded in YEARS so the experience
    # coefficient is "rating points per year" -- lets us translate the
    # protected-factor coefficients into years-equivalent.
    raw_party = np.array([LEVELS["party"][r["party"]] for r in parsed], dtype=float)
    raw_pkg = np.array([LEVELS["policy_package"][r["policy_package"]] for r in parsed], dtype=float)
    raw_exp_yrs = np.array([EXPERIENCE_YEARS[r["experience"]] for r in parsed], dtype=float)
    raw_rig = np.array([LEVELS["rigor"][r["rigor"]] for r in parsed], dtype=float)
    raw_intx = raw_party * raw_pkg
    X_raw = np.column_stack([np.ones(len(y)), raw_party, raw_pkg, raw_intx, raw_exp_yrs, raw_rig])
    names_raw = ["intercept", "party", "policy_package", "party_x_pkg", "experience_yrs", "rigor"]
    b_raw, se_raw, _, _, _ = _ols(X_raw, y)
    beta_raw_d = dict(zip(names_raw, b_raw, strict=False))
    se_raw_d = dict(zip(names_raw, se_raw, strict=False))

    # Years-equivalent translation. Sign convention: positive means the
    # "1" direction of the protected variable (D->R for party,
    # D-typical->R-typical for package) is rated like LOSING that many
    # years of experience.
    yrs_per_yr = beta_raw_d["experience_yrs"]
    if abs(yrs_per_yr) < 1e-9:
        yrs_per_party = None
        yrs_per_package = None
    else:
        yrs_per_party = -beta_raw_d["party"] / yrs_per_yr
        yrs_per_package = -beta_raw_d["policy_package"] / yrs_per_yr

    return FitResult(
        model=model,
        n_total=n_total, n_parsed=n_parsed,
        rating_mean=rating_mean, rating_sd=rating_sd, r2_std=r2,
        beta_std=dict(zip(names_std, b_std, strict=False)),
        se_std=dict(zip(names_std, se_std, strict=False)),
        p_std=dict(zip(names_std, p_std, strict=False)),
        ci_std=ci_std,
        beta_raw=beta_raw_d, se_raw=se_raw_d,
        years_per_party=yrs_per_party,
        years_per_package=yrs_per_package,
    )


# ---- driver ---------------------------------------------------------------

async def main() -> None:
    client = _openrouter_client()
    fits: list[FitResult] = []
    all_rows: list[dict] = []
    for model in MODELS:
        print(f"\n=== {model} ===", flush=True)
        try:
            rows = await gather_for_model(client, model)
        except Exception as e:
            print(f"  failed at top level: {type(e).__name__}: {e}")
            continue
        all_rows.extend(rows)
        fit = fit_model(rows, model)
        fits.append(fit)
        if fit.n_parsed < 30:
            print(f"  parsed only {fit.n_parsed}/{fit.n_total} ratings; skipping fit.")
            continue
        print(
            f"  parsed {fit.n_parsed}/{fit.n_total}, rating_mean={fit.rating_mean:.2f}, "
            f"sd={fit.rating_sd:.2f}, R2={fit.r2_std:.3f}"
        )
        for term in ("party", "policy_package", "party_x_pkg"):
            b = fit.beta_std[term]
            p = fit.p_std[term]
            stars = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else ""))
            print(f"  beta_std[{term:<14}] = {b:+.3f}  p={p:.2e}  {stars}")
        if fit.years_per_party is not None and fit.years_per_package is not None:
            print(
                f"  years-equivalent: party (D->R) = {fit.years_per_party:+.2f} yr,  "
                f"package (D-typ -> R-typ) = {fit.years_per_package:+.2f} yr"
            )

    print("\n" + "=" * 110)
    print("SUMMARY: standardized policy_package beta + years-equivalent translation")
    print("=" * 110)
    print(
        f"{'model':<40} {'n':>4} {'rate_sd':>7} {'beta_pkg':>9} {'p_pkg':>10} "
        f"{'beta_party':>10} {'p_party':>10} {'yrs/pkg':>9} {'yrs/party':>10}"
    )
    for fit in fits:
        if fit.n_parsed < 30:
            print(f"{fit.model:<40} {fit.n_parsed:>4}  insufficient data")
            continue
        print(
            f"{fit.model:<40} {fit.n_parsed:>4} {fit.rating_sd:>7.2f} "
            f"{fit.beta_std.get('policy_package', float('nan')):>+9.3f} "
            f"{fit.p_std.get('policy_package', float('nan')):>10.2e} "
            f"{fit.beta_std.get('party', float('nan')):>+10.3f} "
            f"{fit.p_std.get('party', float('nan')):>10.2e} "
            f"{(fit.years_per_package if fit.years_per_package is not None else float('nan')):>+9.2f} "
            f"{(fit.years_per_party if fit.years_per_party is not None else float('nan')):>+10.2f}"
        )

    out_path = REPO_ROOT / "analysis" / "multi_model_rows.json"
    out_path.write_text(json.dumps(all_rows, indent=2, default=str))
    print(f"\nRaw rows saved to {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
