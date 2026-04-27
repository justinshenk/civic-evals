"""Token-logprob uncertainty: a non-judge UQ signal.

Mean negative log-probability over the generated tokens is the simplest
intrinsic uncertainty signal a model can give: lower mean -logprob = the
model assigned higher probability to its own answer = it was more sure.
This is one of the baseline UQ methods in Vashurin et al. (TACL 2025,
"Benchmarking UQ Methods for LLMs with LM-Polygraph") and the cheapest
to compute — no extra forward passes, no judge.

Provider support:
- OpenAI exposes per-token logprobs (set ``logprobs=True`` in generate
  config).
- Anthropic does **not** expose token logprobs in its public API. Runs
  against Anthropic models will produce ``parse_success=False`` and
  ``value=None``; the scorer fails *quietly* — it does not block the
  run. Aggregate metrics will simply have fewer rows for Anthropic
  subjects until that changes.

Wiring an eval to use this scorer:
    Task(
        ...,
        solver=chain(generate(logprobs=True), ...),
        scorer=token_logprob_uncertainty(),
    )

The score's ``value`` is on [0, 1] where higher = more certain
(``1 / (1 + mean_neg_logprob)``). Use it as a complementary signal to
``rubric_judge.calibrated_uncertainty``: when the two disagree (judge
calls the answer hedged but logprobs are very tight, or vice versa)
that's the interesting case for downstream analysis.
"""

from __future__ import annotations

import math

from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState


@scorer(metrics=[mean()])
def token_logprob_uncertainty() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        logprobs = _extract_logprobs(state)
        if not logprobs:
            # Score.value can't be None; use 0.0 as a sentinel and rely
            # on parse_success=False to filter at the rollup layer. The
            # rollup's calibration_stats already gates on per-row data
            # availability, so this won't poison aggregates.
            return Score(
                value=0.0,
                explanation=(
                    "no token logprobs in output (provider does not expose them, "
                    "or generate(logprobs=True) was not set)"
                ),
                metadata={"parse_success": False, "n_tokens": 0},
            )

        mean_neg_logprob = -sum(logprobs) / len(logprobs)
        # Map [0, ∞) → (0, 1] so the value column behaves like every
        # other scorer's. Higher = more confident. A 1-token
        # near-deterministic completion has neg_logprob ≈ 0 → value ≈ 1.
        confidence = 1.0 / (1.0 + mean_neg_logprob)

        # Per-token range gives a quick sense of how flat the
        # distribution was — useful when sorting through cases.
        max_neg = -min(logprobs)
        min_neg = -max(logprobs)

        return Score(
            value=confidence,
            explanation=(
                f"n={len(logprobs)} tokens, mean -logprob={mean_neg_logprob:.3f} "
                f"(range [{min_neg:.3f}, {max_neg:.3f}])"
            ),
            metadata={
                "parse_success": True,
                "n_tokens": len(logprobs),
                "mean_neg_logprob": mean_neg_logprob,
                "max_neg_logprob": max_neg,
                "min_neg_logprob": min_neg,
            },
        )

    return score


def _extract_logprobs(state: TaskState) -> list[float]:
    """Pull per-token logprobs from inspect-ai's model output structure.

    Returns an empty list if logprobs aren't present — the scorer's
    contract is to no-op rather than crash so cross-provider rollups
    aren't broken by one provider's silence.
    """
    output = getattr(state, "output", None)
    if output is None:
        return []
    choices = getattr(output, "choices", None) or []
    if not choices:
        return []
    lp = getattr(choices[0], "logprobs", None)
    if lp is None:
        return []
    content = getattr(lp, "content", None) or []
    out: list[float] = []
    for tok in content:
        v = getattr(tok, "logprob", None)
        if isinstance(v, (int, float)) and math.isfinite(v):
            out.append(float(v))
    return out
