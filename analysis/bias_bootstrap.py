"""Bootstrap CIs for the cross-model school-board bias result.

Stage 1 of the platform-coding manipulation check (see
`platform_coding_check_results.md`). `multi_model_results.md` reports
point estimates only; before explaining why DeepSeek and Qwen show the
smallest policy-package effect, check whether that gap survives
sampling noise.

For each model, resample its rows with replacement, re-fit the same OLS
(`multi_model_bias.fit_model`), and collect beta_package (standardized),
years/package and years/party. Reports 95% percentile CIs per model and
for pairwise differences (DeepSeek/Qwen minus each other model). Models
are sampled independently, so a pairwise difference is the difference
of independent bootstrap draws.

No API calls -- reads `analysis/multi_model_rows.json`.

Usage:
    uv run python analysis/bias_bootstrap.py [--n-boot 5000] [--seed 0]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from multi_model_bias import MODELS, fit_model  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
ROWS_PATH = REPO_ROOT / "analysis" / "multi_model_rows.json"
OUT_PATH = REPO_ROOT / "analysis" / "bias_bootstrap_results.json"

METRICS = ("beta_package", "years_per_package", "years_per_party")
FOCUS_MODELS = ("deepseek/deepseek-chat", "qwen/qwen-2.5-72b-instruct")


def _metrics_from_rows(rows: list[dict], model: str) -> dict[str, float]:
    fit = fit_model(rows, model)
    nan = float("nan")
    return {
        "beta_package": fit.beta_std.get("policy_package", nan),
        "years_per_package": fit.years_per_package if fit.years_per_package is not None else nan,
        "years_per_party": fit.years_per_party if fit.years_per_party is not None else nan,
    }


def bootstrap_model(
    rows: list[dict], model: str, n_boot: int, rng: np.random.Generator
) -> dict[str, np.ndarray]:
    """Return {metric: array of n_boot bootstrap draws} for one model.

    Only parsed rows are resampled, so every draw has the same n as the
    original fit.
    """
    parsed = [r for r in rows if isinstance(r.get("rating"), (int, float))]
    n = len(parsed)
    draws: dict[str, list[float]] = {m: [] for m in METRICS}
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        sample = [parsed[i] for i in idx]
        try:
            vals = _metrics_from_rows(sample, model)
        except np.linalg.LinAlgError:
            vals = {m: float("nan") for m in METRICS}
        for m in METRICS:
            draws[m].append(vals[m])
    return {m: np.asarray(v, dtype=float) for m, v in draws.items()}


def ci(arr: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    a = arr[np.isfinite(arr)]
    if a.size == 0:
        return (float("nan"), float("nan"))
    lo = (1 - level) / 2 * 100
    return (float(np.percentile(a, lo)), float(np.percentile(a, 100 - lo)))


def run(rows: list[dict], n_boot: int, seed: int, models: list[str] | None = None) -> dict:
    rng = np.random.default_rng(seed)
    models = models or [m for m in MODELS if any(r["model"] == m for r in rows)]
    by_model = {m: [r for r in rows if r["model"] == m] for m in models}

    point: dict[str, dict[str, float]] = {}
    draws: dict[str, dict[str, np.ndarray]] = {}
    for m in models:
        point[m] = _metrics_from_rows(by_model[m], m)
        draws[m] = bootstrap_model(by_model[m], m, n_boot, rng)

    per_model = {
        m: {
            metric: {"estimate": point[m][metric], "ci95": ci(draws[m][metric])}
            for metric in METRICS
        }
        for m in models
    }

    pairwise: list[dict] = []
    for focus in FOCUS_MODELS:
        if focus not in draws:
            continue
        for other in models:
            if other == focus:
                continue
            entry = {"focus": focus, "other": other}
            for metric in ("beta_package", "years_per_package"):
                diff = draws[focus][metric] - draws[other][metric]
                lo, hi = ci(diff)
                entry[metric] = {
                    "estimate": point[focus][metric] - point[other][metric],
                    "ci95": (lo, hi),
                    "excludes_zero": bool(lo > 0 or hi < 0),
                }
            pairwise.append(entry)

    return {"n_boot": n_boot, "seed": seed, "per_model": per_model, "pairwise": pairwise}


def _fmt_ci(d: dict, prec: int) -> str:
    lo, hi = d["ci95"]
    return f"{d['estimate']:+.{prec}f} [{lo:+.{prec}f}, {hi:+.{prec}f}]"


def print_report(res: dict) -> None:
    print(f"Bootstrap: {res['n_boot']} resamples per model, seed={res['seed']}\n")
    print(f"{'model':<38} {'beta_pkg (std)':>26} {'yrs/package':>24} {'yrs/party':>24}")
    for m, d in res["per_model"].items():
        print(
            f"{m:<38} {_fmt_ci(d['beta_package'], 3):>26} "
            f"{_fmt_ci(d['years_per_package'], 2):>24} {_fmt_ci(d['years_per_party'], 2):>24}"
        )
    print("\nPairwise differences (focus - other); * = 95% CI excludes 0")
    print(f"{'focus':<28} {'other':<38} {'d beta_pkg':>28} {'d yrs/package':>28}")
    for p in res["pairwise"]:
        b, y = p["beta_package"], p["years_per_package"]
        print(
            f"{p['focus']:<28} {p['other']:<38} "
            f"{_fmt_ci(b, 3) + (' *' if b['excludes_zero'] else '  '):>28} "
            f"{_fmt_ci(y, 2) + (' *' if y['excludes_zero'] else '  '):>28}"
        )


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rows", type=Path, default=ROWS_PATH)
    ap.add_argument("--n-boot", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args(argv)

    rows = json.loads(args.rows.read_text())
    res = run(rows, args.n_boot, args.seed)
    print_report(res)
    args.out.write_text(json.dumps(res, indent=2))
    print(f"\nSaved {args.out.relative_to(REPO_ROOT) if args.out.is_relative_to(REPO_ROOT) else args.out}")


if __name__ == "__main__":
    main()
