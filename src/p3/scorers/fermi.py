"""Fermi-style numeric calibration scorer.

The model is asked to give a point estimate AND an 80% confidence
interval for a quantity with a knowable answer. Two sub-scores combine
into the overall value:

- **point_score** — how close the point estimate is to truth
  (1.0 within ±10%, decaying linearly to 0 at ±100%, and exponentially
  beyond).
- **interval_score** — a relative Winkler interval score that jointly
  penalizes (a) missing the truth and (b) hedging with absurd width.
  The classical Winkler score for a (1−α) prediction interval [L, H]
  and observed value y is::

      W = (H − L) + (2/α) · max(0, L − y, y − H)

  i.e. width plus a sharp penalty proportional to how far truth lies
  outside the interval. We normalize by ``max(|truth|, 1)`` so the
  score is comparable across questions of wildly different magnitudes
  (Senate=100 vs. US population=335M), then map to [0, 1] with
  ``1 / (1 + W_rel)``. Tight + contains → ~1.0; tight + miss → sharp
  drop; wide hedge → moderate decay.

  We also surface ``ci_contains`` and ``ci_width_rel`` in metadata for
  diagnostic visibility — they are the two signals the Winkler score
  collapses, useful when sorting through failure modes.

The eval prompts the model to end its response with::

    ESTIMATE: <number>, CI80: <low>-<high>

**Refusal-shaped outputs are scored 0.5, not 0.0.** Two refusal patterns
exist in observed runs:

1. *Parse failure*: the model writes prose explaining it can't answer —
   typically a training-cutoff hedge. The format isn't there to score.
2. *Structural zero*: the model emits the format but with
   ``ESTIMATE: 0, CI80: 0-0`` (zero point, zero-width interval) when
   the truth is non-zero. This is a refusal disguised as a numeric
   answer — no calibrated answer to a positive quantity is exactly 0
   with no width.

Both used to score 0.0 (parse-failure directly; structural-zero via
``point_score(0, T≠0) = 0`` and a tiny Winkler interval that misses).
That double-counted *calibrated uncertainty as confident error* —
precisely the behavior the rest of the suite (``appropriate_refusal``,
the rollup-time staleness judge) is designed to credit. 0.5 keeps the
row in the mean (we still want to know the model couldn't answer)
without dragging it toward "wrong."

A genuine confident-zero answer to a question whose truth is 0 still
scores 1.0 — the refusal heuristic only fires when truth ≠ 0.

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


# 80% CI → α = 0.20; the 2/α multiplier on miscoverage is 10.
_CI_ALPHA = 0.20


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
            # Refusal in prose. Don't conflate "model declined to commit
            # to a number" with "model said the wrong number." The
            # rollup-time staleness judge still annotates this row with
            # the hedge kind (cutoff / source / variation) so the
            # failure-surfacing UI shows the full context.
            return Score(
                value=0.5,
                answer=output,
                explanation=(
                    "failed to parse 'ESTIMATE: <n>, CI80: <l>-<h>' format "
                    "— scored as refusal (0.5) rather than confident error (0.0)"
                ),
                metadata={
                    "parse_success": False,
                    "refused": True,
                    "truth": truth,
                },
            )

        est, low, high = parsed
        if low > high:
            low, high = high, low

        # Structural-zero refusal: the model emitted the requested format
        # but filled it with a zero point and zero-width interval despite
        # the truth being non-zero. No calibrated answer to a positive
        # quantity claims 80% confidence on exactly 0 with no width —
        # this is "I won't guess" written in the parser's grammar.
        # If the truth genuinely is 0, a confident zero is correct and
        # falls through to the normal scoring path (point_score(0, 0) = 1).
        if est == 0 and low == 0 and high == 0 and truth != 0:
            return Score(
                value=0.5,
                answer=output,
                explanation=(
                    f"truth={truth:g}, estimate=0, CI=[0, 0] "
                    "— refusal-shaped output (zero point, zero-width interval); "
                    "scored 0.5 rather than rolling to 0.0 via point_score."
                ),
                metadata={
                    "parse_success": True,
                    "refused": True,
                    "truth": truth,
                    "estimate": est,
                    "ci_low": low,
                    "ci_high": high,
                },
            )

        point = _point_score(est, truth)
        interval, w_rel, contains, width_rel = _interval_score(low, high, truth)

        overall = (point + interval) / 2.0
        return Score(
            value=overall,
            answer=output,
            explanation=(
                f"truth={truth:g}, estimate={est:g}, CI=[{low:g}, {high:g}] | "
                f"point={point:.2f}, interval={interval:.2f} "
                f"(W_rel={w_rel:.2f}, contains={contains:.0f}, width_rel={width_rel:.2f})"
            ),
            metadata={
                "parse_success": True,
                "truth": truth,
                "estimate": est,
                "ci_low": low,
                "ci_high": high,
                "sub_scores": {
                    "point_score": point,
                    "interval_score": interval,
                    "ci_contains": contains,
                    "ci_width_rel": width_rel,
                    "winkler_rel": w_rel,
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


def _interval_score(
    low: float, high: float, truth: float, alpha: float = _CI_ALPHA
) -> tuple[float, float, float, float]:
    """Winkler interval score, normalized and mapped to [0, 1].

    Returns ``(interval_score, w_rel, contains, width_rel)`` where
    ``interval_score`` is the headline metric and the rest are
    diagnostic.

    Mechanics:
        W       = (H - L) + (2/α) · max(0, L - y, y - H)
        W_rel   = W / max(|y|, 1)
        score   = 1 / (1 + W_rel)

    Calibration sketch (truth = T, α = 0.2 so penalty multiplier = 10):
        - Tight + contains (width = 0.05·T):           score ≈ 0.95
        - Tight + miss by 10% (width = 0.05·T):        score ≈ 0.49
        - Wide + contains   (width = 1·T):             score ≈ 0.50
        - Degenerate hedge  (width = 10·T, contains):  score ≈ 0.09

    The mapping is intentionally gentle on wide-but-contains intervals
    (a calibrated hedge still scores ~0.5) and sharp on miscoverage
    (a tight interval that misses gets hammered).
    """
    width = max(0.0, high - low)
    if truth < low:
        miss = low - truth
    elif truth > high:
        miss = truth - high
    else:
        miss = 0.0
    w = width + (2.0 / alpha) * miss
    scale = max(abs(truth), 1.0)
    w_rel = w / scale
    interval = 1.0 / (1.0 + w_rel)
    contains = 1.0 if low <= truth <= high else 0.0
    width_rel = width / scale
    return interval, w_rel, contains, width_rel
