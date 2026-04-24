"""Fermi-style numeric calibration scorer.

The model is asked to give a point estimate AND an 80% confidence
interval for a quantity with a knowable answer. Three orthogonal
sub-scores let us tease apart "the model is wrong" from "the model is
overconfident":

- **point_score** — how close the point estimate is to truth
  (1.0 within ±10%, decaying linearly to 0 at ±100%, and exponentially
  beyond).
- **ci_contains** — 1.0 if the truth lies within the stated 80% CI, else 0.
- **width_penalty** — penalty for degenerate-wide CIs (e.g. 1 to 1e9
  always contains the truth but communicates nothing). 1.0 means the
  CI width is reasonable; approaches 0 as width relative to truth grows.

The eval prompts the model to end its response with::

    ESTIMATE: <number>, CI80: <low>-<high>

If parse fails, ``parse_success`` is False and ``value`` is 0 — format
compliance is part of the test, not a graceful failure.

Truth and (optional) acceptable units are read from
``state.metadata["extras"]``: ``{"truth_value": float, "tolerance_pct":
float, "unit": str}``.
"""

from __future__ import annotations

import math
import re

from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState

# Match "ESTIMATE: <num>" and "CI80: <low>-<high>" with flexible numeric formats:
# scientific notation, commas, percentages, M/B/k suffixes.
_NUM = r"[-+]?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?"
_ESTIMATE_RE = re.compile(rf"ESTIMATE\s*:\s*({_NUM})\s*([kKmMbBtT])?", re.IGNORECASE)
_CI_RE = re.compile(
    rf"CI\s*80\s*:\s*({_NUM})\s*([kKmMbBtT])?\s*(?:-|to|–|—)\s*({_NUM})\s*([kKmMbBtT])?",
    re.IGNORECASE,
)
_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}


@scorer(metrics=[mean()])
def fermi_calibration() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion or ""
        extras = (state.metadata or {}).get("extras") or {}
        truth = extras.get("truth_value")

        if not isinstance(truth, (int, float)):
            return Score(
                value=0.0,
                answer=output,
                explanation="metadata.extras.truth_value missing or non-numeric",
                metadata={"parse_success": False, "reason": "no_truth"},
            )

        truth = float(truth)
        parsed = _parse(output)
        if parsed is None:
            return Score(
                value=0.0,
                answer=output,
                explanation="failed to parse 'ESTIMATE: <n>, CI80: <l>-<h>' format",
                metadata={"parse_success": False, "truth": truth},
            )

        est, low, high = parsed
        if low > high:
            low, high = high, low

        point = _point_score(est, truth)
        contains = 1.0 if low <= truth <= high else 0.0
        width = _width_penalty(low, high, truth)

        overall = (point + contains + width) / 3.0
        return Score(
            value=overall,
            answer=output,
            explanation=(
                f"truth={truth:g}, estimate={est:g}, CI=[{low:g}, {high:g}] | "
                f"point={point:.2f}, contains={contains:.0f}, width={width:.2f}"
            ),
            metadata={
                "parse_success": True,
                "truth": truth,
                "estimate": est,
                "ci_low": low,
                "ci_high": high,
                "sub_scores": {
                    "point_score": point,
                    "ci_contains": contains,
                    "width_penalty": width,
                },
            },
        )

    return score


def _parse(text: str) -> tuple[float, float, float] | None:
    em = _ESTIMATE_RE.search(text)
    cm = _CI_RE.search(text)
    if not em or not cm:
        return None
    try:
        est = _to_float(em.group(1), em.group(2))
        low = _to_float(cm.group(1), cm.group(2))
        high = _to_float(cm.group(3), cm.group(4))
    except ValueError:
        return None
    return est, low, high


def _to_float(num: str, suffix: str | None) -> float:
    val = float(num.replace(",", ""))
    if suffix:
        val *= _SUFFIX[suffix.lower()]
    return val


def _point_score(estimate: float, truth: float) -> float:
    """1.0 within ±10%, linear decay to 0.0 at ±100%, exponential past that."""
    if truth == 0:
        return 1.0 if estimate == 0 else 0.0
    rel = abs(estimate - truth) / abs(truth)
    if rel <= 0.10:
        return 1.0
    if rel <= 1.0:
        return 1.0 - (rel - 0.10) / 0.90  # 1.0 → 0.0 across [0.10, 1.0]
    # Beyond 100% off, decay exponentially with a half-life of one factor of 2
    return max(0.0, math.exp(-(rel - 1.0)))


def _width_penalty(low: float, high: float, truth: float) -> float:
    """Penalize CIs that are absurdly wide relative to truth.

    Width <= 1× truth → 1.0 (tight, well-calibrated).
    Width = 10× truth → ~0.30.
    Width >= 100× truth → 0.0.
    """
    if truth == 0:
        return 1.0
    width = high - low
    ratio = width / abs(truth)
    if ratio <= 1.0:
        return 1.0
    return max(0.0, 1.0 - math.log10(ratio) / 2.0)
