"""civic_bias_experiment.py -- general infrastructure for variance-
decomposition / regression-style experiments on LLM civic-information
responses.

Given:
  - A list of civic questions
  - A set of factors to vary (some "should not matter," some "should matter")
  - A list of Anthropic models to run against
  - A number of replicates per cell

This module:
  1. Renders every combination (question x factor levels) as a prompt pair
     (system + user) using string substitution on caller-provided templates.
  2. Dispatches calls to the Anthropic Messages API with bounded concurrency.
  3. Parses a numeric score from each response (default: RATING: <n>).
  4. Fits per-question and pooled OLS with standardized coefficients,
     pairwise interactions among protected factors, and question fixed
     effects in the pooled fit.
  5. Persists raw rows + fits as JSON for re-analysis.

Factor injection is implicit: factors don't declare where to go. The
caller writes system_prompt_template and user_prompt_template that
reference {factor_name} placeholders; ``str.format`` substitutes at
render time. Persona factors typically appear in the system template,
question-internal factors in the user template, but the templates can
mix both freely.

Predicted-cost helper: ``estimate_cost(config)`` returns a per-model
breakdown and a total in dollars, using a price table the caller can
update for fresh model pricing. The estimate is conservative -- it
assumes a fixed avg input/output token count per call.

Usage:
    cfg = ExperimentConfig(...)
    print(estimate_cost(cfg))                  # cost before running
    rows = asyncio.run(run(cfg))               # actually run
    fits = fit_all(rows, cfg)                  # regression analysis
    persist(rows, fits, out_dir="analysis/")   # save raw + fits

Dependencies:
    - anthropic (for the AsyncAnthropic client)
    - numpy + scipy.stats (for OLS + p-values)
    - python-dotenv (for ANTHROPIC_API_KEY loading)

Cross-provider coverage (OpenAI / Google / Llama / DeepSeek / Qwen) lives
in the separate ``multi_model_bias.py`` script which uses OpenRouter.
This module is intentionally Anthropic-direct so we burn Anthropic
credits rather than pay-per-call OpenRouter charges, and so the run
behavior is reproducible without OpenRouter routing variance.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal

import numpy as np
import scipy.stats as stats
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

FactorKind = Literal["protected", "legitimate"]


@dataclass(frozen=True)
class Question:
    """A civic-information question that the model will answer.

    ``text`` is referenced from the templates as ``{question_text}``.
    ``metadata`` is free-form annotation that propagates into the rows
    (e.g. category, source, difficulty rating) so the analysis can
    slice by it later.
    """

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Factor:
    """A variable to vary in the factorial design.

    ``levels`` is an ordered tuple of human-readable strings -- these
    are the values substituted into the prompt templates via
    ``{name}`` placeholders.

    ``ordinal`` optionally maps each level string to a numeric value
    used for the regression encoding. If None, the level index is
    used (0, 1, 2, ...) which is fine for the headline standardized
    coefficients but ignores any monotonic structure (e.g. years).
    Provide ordinal explicitly when you want trade-off translations
    in raw units.

    ``kind`` separates protected (should not matter) from legitimate
    (should matter) factors. Headline metrics compare the largest
    protected coefficient to the largest legitimate coefficient.
    """

    name: str
    levels: tuple[str, ...]
    ordinal: dict[str, float] | None = None
    kind: FactorKind = "protected"

    def ordinal_for(self, level: str) -> float:
        if self.ordinal is not None:
            return float(self.ordinal[level])
        return float(self.levels.index(level))


@dataclass
class ExperimentConfig:
    """Configuration for one experiment run.

    Templates are caller-provided str.format strings. Available
    placeholders are ``{question_text}`` (always) plus the name of
    every Factor in ``factors``.
    """

    name: str
    questions: list[Question]
    factors: list[Factor]
    system_prompt_template: str = ""
    user_prompt_template: str = "{question_text}"
    models: list[str] = field(default_factory=list)
    n_reps: int = 5
    max_concurrency: int = 8
    max_tokens: int = 1024
    rating_pattern: str = r"RATING\s*:\s*(\d+(?:\.\d+)?)"
    rating_range: tuple[float, float] = (1.0, 10.0)

    def factor_by_name(self, name: str) -> Factor | None:
        for f in self.factors:
            if f.name == name:
                return f
        return None

    def cells_per_question(self) -> int:
        n = 1
        for f in self.factors:
            n *= len(f.levels)
        return n

    def total_calls(self) -> int:
        return (
            len(self.questions)
            * self.cells_per_question()
            * self.n_reps
            * max(1, len(self.models))
        )


# ---------------------------------------------------------------------------
# Prompt rendering + response parsing
# ---------------------------------------------------------------------------


def _factor_assignments(factors: list[Factor]) -> list[dict[str, str]]:
    """Cartesian product of factor levels -> list of {name: level} dicts."""
    if not factors:
        return [{}]
    levels = [(f.name, f.levels) for f in factors]
    out = []
    for combo in itertools.product(*[lv for _, lv in levels]):
        out.append({name: val for (name, _), val in zip(levels, combo)})
    return out


def render(
    config: ExperimentConfig, question: Question, assignment: dict[str, str]
) -> tuple[str, str]:
    """Format the system + user prompts for one cell."""
    fmt_args = {"question_text": question.text, **assignment}
    system_prompt = config.system_prompt_template.format(**fmt_args)
    user_prompt = config.user_prompt_template.format(**fmt_args)
    return system_prompt, user_prompt


def parse_rating(text: str, pattern: str, lo: float, hi: float) -> float | None:
    m = re.search(pattern, text or "", re.IGNORECASE)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except (ValueError, IndexError):
        return None
    if not (lo <= v <= hi):
        return None
    return v


# ---------------------------------------------------------------------------
# Dispatch (Anthropic Messages API)
# ---------------------------------------------------------------------------


def _client() -> AsyncAnthropic:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY missing from environment / .env"
        )
    return AsyncAnthropic(api_key=key)


async def _one_call(
    client: AsyncAnthropic,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
) -> tuple[str, dict[str, int] | None]:
    """Return (response text, usage dict or None on failure).

    Anthropic's Messages API takes the system prompt as a top-level
    ``system`` kwarg, not as a message role. We pass it that way when
    non-empty, and omit the kwarg otherwise so the request is identical
    in shape to a plain user-message call.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    try:
        resp = await client.messages.create(**kwargs)
        text = "".join(
            getattr(b, "text", "") for b in resp.content if hasattr(b, "text")
        )
        usage = None
        if getattr(resp, "usage", None) is not None:
            usage = {
                "prompt_tokens": int(getattr(resp.usage, "input_tokens", 0) or 0),
                "completion_tokens": int(
                    getattr(resp.usage, "output_tokens", 0) or 0
                ),
            }
        return text, usage
    except Exception as e:
        return f"<error: {type(e).__name__}: {e}>", None


async def run(config: ExperimentConfig) -> list[dict[str, Any]]:
    """Run the experiment. Returns a list of row dicts."""
    if not config.models:
        raise ValueError("ExperimentConfig.models is empty")
    client = _client()
    sem = asyncio.Semaphore(config.max_concurrency)
    assignments = _factor_assignments(config.factors)

    async def one_row(
        model: str, q: Question, assignment: dict[str, str], rep: int
    ) -> dict[str, Any]:
        system_prompt, user_prompt = render(config, q, assignment)
        async with sem:
            text, usage = await _one_call(
                client, model, system_prompt, user_prompt, config.max_tokens
            )
        rating = parse_rating(
            text, config.rating_pattern, *config.rating_range
        )
        row: dict[str, Any] = {
            "experiment": config.name,
            "model": model,
            "question_id": q.id,
            "rep": rep,
            "rating": rating,
            "response_chars": len(text),
            "system_prompt_chars": len(system_prompt),
            "user_prompt_chars": len(user_prompt),
        }
        if usage:
            row.update(usage)
        for k, v in assignment.items():
            row[k] = v
        if q.metadata:
            row["question_metadata"] = q.metadata
        return row

    coros = [
        one_row(model, q, assignment, rep)
        for model in config.models
        for q in config.questions
        for assignment in assignments
        for rep in range(config.n_reps)
    ]
    return await asyncio.gather(*coros)


# ---------------------------------------------------------------------------
# Regression analysis
# ---------------------------------------------------------------------------


def _z(col: np.ndarray) -> np.ndarray:
    sd = col.std(ddof=0)
    return (col - col.mean()) / sd if sd > 1e-9 else col - col.mean()


def _ols(
    X: np.ndarray, y: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, int, float]:
    """Returns (beta, se, t, p_two_sided, df, R^2)."""
    n, p = X.shape
    df = n - p
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    sigma2 = (resid @ resid) / df if df > 0 else float("nan")
    var_beta = sigma2 * XtX_inv
    se = np.sqrt(np.diag(var_beta))
    t = beta / se if (se > 0).all() else beta * np.nan
    p = 2 * stats.t.sf(np.abs(t), df=df)
    y_hat = X @ beta
    ss_res = float(((y - y_hat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return beta, se, t, p, df, r2


def _build_design(
    rows: list[dict[str, Any]],
    config: ExperimentConfig,
    include_question_fixed_effects: bool,
) -> tuple[np.ndarray, list[str], np.ndarray]:
    """Build the design matrix for OLS.

    Columns: intercept, each factor (z-scored), all pairwise interactions
    among protected factors (z-scored), optionally one dummy per question
    (omit reference question to avoid collinearity).
    Returns (X, column_names, y).
    """
    parsed = [r for r in rows if isinstance(r.get("rating"), (int, float))]
    n = len(parsed)
    y = np.array([r["rating"] for r in parsed], dtype=float)
    if n < 2 or y.std(ddof=0) < 1e-9:
        return np.empty((0, 0)), [], y

    # Z-score the response.
    y_z = _z(y)

    factor_cols: dict[str, np.ndarray] = {}
    for f in config.factors:
        raw = np.array([f.ordinal_for(r[f.name]) for r in parsed], dtype=float)
        factor_cols[f.name] = _z(raw)

    cols = [np.ones(n)]
    names = ["intercept"]
    for f in config.factors:
        cols.append(factor_cols[f.name])
        names.append(f.name)

    # Pairwise interactions among protected factors.
    protected = [f for f in config.factors if f.kind == "protected"]
    for i in range(len(protected)):
        for j in range(i + 1, len(protected)):
            a, b = protected[i].name, protected[j].name
            inter = factor_cols[a] * factor_cols[b]
            cols.append(_z(inter))
            names.append(f"{a}_x_{b}")

    if include_question_fixed_effects and len(config.questions) > 1:
        # One dummy per question except the first (the reference).
        qids = [q.id for q in config.questions]
        ref = qids[0]
        for qid in qids[1:]:
            d = np.array([1.0 if r["question_id"] == qid else 0.0 for r in parsed])
            cols.append(d)
            names.append(f"qfx[{qid}]")

    X = np.column_stack(cols)
    return X, names, y_z


@dataclass
class FitResult:
    n_total: int
    n_parsed: int
    df: int
    r2: float
    rating_mean: float
    rating_sd: float
    beta: dict[str, float]
    se: dict[str, float]
    p: dict[str, float]
    ci95: dict[str, tuple[float, float]]


def _fit_subset(rows: list[dict[str, Any]], config: ExperimentConfig, fe: bool) -> FitResult:
    X, names, y_z = _build_design(rows, config, include_question_fixed_effects=fe)
    parsed = [r for r in rows if isinstance(r.get("rating"), (int, float))]
    n_total = len(rows)
    n_parsed = len(parsed)
    if n_parsed < 5 or X.shape[0] == 0:
        return FitResult(
            n_total=n_total, n_parsed=n_parsed, df=0, r2=float("nan"),
            rating_mean=float("nan"), rating_sd=float("nan"),
            beta={}, se={}, p={}, ci95={},
        )
    beta, se, _, p, df, r2 = _ols(X, y_z)
    crit = stats.t.ppf(0.975, df=df) if df > 0 else float("nan")
    ratings = np.array([r["rating"] for r in parsed], dtype=float)
    return FitResult(
        n_total=n_total, n_parsed=n_parsed, df=df, r2=r2,
        rating_mean=float(ratings.mean()), rating_sd=float(ratings.std(ddof=0)),
        beta={n: float(b) for n, b in zip(names, beta)},
        se={n: float(s) for n, s in zip(names, se)},
        p={n: float(pp) for n, pp in zip(names, p)},
        ci95={
            n: (float(b - crit * s), float(b + crit * s))
            for n, b, s in zip(names, beta, se)
        },
    )


def fit_per_question(
    rows: list[dict[str, Any]], config: ExperimentConfig
) -> dict[str, dict[str, FitResult]]:
    """Fit one regression per (model, question_id) pair.

    Returns a nested dict: {model: {question_id: FitResult}}.
    """
    by_mq: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        by_mq.setdefault((r["model"], r["question_id"]), []).append(r)
    out: dict[str, dict[str, FitResult]] = {}
    for (model, qid), sub in by_mq.items():
        out.setdefault(model, {})[qid] = _fit_subset(sub, config, fe=False)
    return out


def fit_pooled(
    rows: list[dict[str, Any]], config: ExperimentConfig
) -> dict[str, FitResult]:
    """Fit a pooled regression per model, with question fixed effects."""
    by_m: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_m.setdefault(r["model"], []).append(r)
    return {m: _fit_subset(sub, config, fe=True) for m, sub in by_m.items()}


def fit_all(
    rows: list[dict[str, Any]], config: ExperimentConfig
) -> dict[str, Any]:
    """Both per-(model, question) and pooled-with-FE fits."""
    return {
        "per_question": fit_per_question(rows, config),
        "pooled": fit_pooled(rows, config),
    }


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


# Anthropic direct-API prices per 1M tokens (input, output). Update as
# prices change; the caller can override via the ``prices`` arg.
# IDs match the model strings the Anthropic SDK accepts.
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-5": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-5": (15.00, 75.00),
    "claude-opus-4-6": (15.00, 75.00),
}


@dataclass
class CostEstimate:
    total_calls: int
    avg_input_tokens: int
    avg_output_tokens: int
    per_model_dollars: dict[str, float]
    total_dollars: float
    unpriced_models: list[str]


def estimate_cost(
    config: ExperimentConfig,
    prices: dict[str, tuple[float, float]] | None = None,
    avg_input_tokens: int = 600,
    avg_output_tokens: int = 700,
) -> CostEstimate:
    """Rough dollar estimate for a config, before running.

    The default avg-token assumptions reflect the candidate-evaluation
    runs in this repo (system prompt + question + a ~400-700 char
    reasoned response ending with RATING). Override if your templates
    are notably bigger or smaller.

    A model not in the price table is reported in ``unpriced_models``
    and contributes $0 to the total -- the caller should add a price
    or remove the model.
    """
    table = {**DEFAULT_PRICES, **(prices or {})}
    cells_per_q = config.cells_per_question()
    calls_per_model = len(config.questions) * cells_per_q * config.n_reps
    per_model: dict[str, float] = {}
    unpriced: list[str] = []
    for m in config.models:
        if m not in table:
            unpriced.append(m)
            per_model[m] = 0.0
            continue
        in_price, out_price = table[m]
        cost_per_call = (
            avg_input_tokens * in_price + avg_output_tokens * out_price
        ) / 1_000_000.0
        per_model[m] = cost_per_call * calls_per_model
    total = sum(per_model.values())
    return CostEstimate(
        total_calls=config.total_calls(),
        avg_input_tokens=avg_input_tokens,
        avg_output_tokens=avg_output_tokens,
        per_model_dollars=per_model,
        total_dollars=total,
        unpriced_models=unpriced,
    )


def format_cost_estimate(est: CostEstimate) -> str:
    lines = [
        f"Total calls:       {est.total_calls:,}",
        f"Token budget/call: ~{est.avg_input_tokens} in / ~{est.avg_output_tokens} out",
        "Per-model dollars:",
    ]
    for m, d in sorted(est.per_model_dollars.items(), key=lambda x: -x[1]):
        lines.append(f"  {m:<40} ${d:7.2f}")
    lines.append(f"TOTAL:             ${est.total_dollars:.2f}")
    if est.unpriced_models:
        lines.append("Unpriced (treated as $0): " + ", ".join(est.unpriced_models))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _fit_to_jsonable(fit: FitResult) -> dict[str, Any]:
    return {
        "n_total": fit.n_total,
        "n_parsed": fit.n_parsed,
        "df": fit.df,
        "r2": fit.r2,
        "rating_mean": fit.rating_mean,
        "rating_sd": fit.rating_sd,
        "beta": fit.beta,
        "se": fit.se,
        "p": fit.p,
        "ci95": {k: list(v) for k, v in fit.ci95.items()},
    }


def persist(
    rows: list[dict[str, Any]],
    fits: dict[str, Any],
    out_dir: str | Path,
    name: str,
) -> tuple[Path, Path]:
    """Write rows + fits to {name}_rows.json and {name}_fits.json."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    rows_path = out_path / f"{name}_rows.json"
    fits_path = out_path / f"{name}_fits.json"

    rows_path.write_text(json.dumps(rows, indent=2, default=str))

    fits_json = {
        "per_question": {
            model: {qid: _fit_to_jsonable(fr) for qid, fr in by_q.items()}
            for model, by_q in fits["per_question"].items()
        },
        "pooled": {model: _fit_to_jsonable(fr) for model, fr in fits["pooled"].items()},
    }
    fits_path.write_text(json.dumps(fits_json, indent=2, default=str))
    return rows_path, fits_path


# ---------------------------------------------------------------------------
# Convenience: short summary printer
# ---------------------------------------------------------------------------


def print_summary(fits: dict[str, Any], config: ExperimentConfig) -> None:
    """Print a one-line-per-model pooled summary table for fast scan."""
    protected_names = [f.name for f in config.factors if f.kind == "protected"]
    legit_names = [f.name for f in config.factors if f.kind == "legitimate"]

    print(f"\n=== Pooled fit (with question fixed effects) for {config.name} ===")
    header = f"{'model':<40} {'n':>6} {'R2':>6} "
    header += " ".join(f"{n:>10}" for n in protected_names + legit_names)
    print(header)
    for model, fit in fits["pooled"].items():
        if fit.n_parsed < 5:
            print(f"{model:<40}  insufficient data ({fit.n_parsed} parsed)")
            continue
        row = f"{model:<40} {fit.n_parsed:>6} {fit.r2:>6.3f} "
        for n in protected_names + legit_names:
            b = fit.beta.get(n, float("nan"))
            p = fit.p.get(n, float("nan"))
            stars = "*" if p < 0.05 else " "
            row += f" {b:>+8.3f}{stars}"
        print(row)
