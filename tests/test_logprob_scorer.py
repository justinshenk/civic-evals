"""Token-logprob scorer behavior — parsing path only (no API).

Tests the no-op contract: when the model output contains no logprobs
(Anthropic, or OpenAI without logprobs=True), the scorer must return
``value=None`` and ``parse_success=False`` rather than crashing. This is
load-bearing because cross-provider rollups would otherwise blow up on
the first Anthropic row.
"""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from p3.scorers.logprob import token_logprob_uncertainty


class _StubTarget:
    pass


def _state(logprobs_list: list[float] | None) -> SimpleNamespace:
    """Construct just enough of a TaskState shape for the scorer to read."""
    if logprobs_list is None:
        choices = [SimpleNamespace(logprobs=None)]
    else:
        content = [
            SimpleNamespace(token=f"t{i}", logprob=lp)
            for i, lp in enumerate(logprobs_list)
        ]
        choices = [SimpleNamespace(logprobs=SimpleNamespace(content=content))]
    output = SimpleNamespace(choices=choices, completion="…")
    return SimpleNamespace(output=output, metadata={})


@pytest.mark.asyncio
async def test_no_logprobs_returns_none() -> None:
    scorer_fn = token_logprob_uncertainty()
    score = await scorer_fn(_state(None), _StubTarget())  # type: ignore[arg-type]
    assert score.value == 0.0
    assert score.metadata["parse_success"] is False
    assert "no token logprobs" in score.explanation.lower()


@pytest.mark.asyncio
async def test_empty_choices_returns_none() -> None:
    scorer_fn = token_logprob_uncertainty()
    state = SimpleNamespace(output=SimpleNamespace(choices=[]), metadata={})
    score = await scorer_fn(state, _StubTarget())  # type: ignore[arg-type]
    assert score.value == 0.0
    assert score.metadata["parse_success"] is False


@pytest.mark.asyncio
async def test_high_confidence_logprobs() -> None:
    scorer_fn = token_logprob_uncertainty()
    # All log p = -0.01: very confident generation.
    score = await scorer_fn(_state([-0.01, -0.01, -0.01]), _StubTarget())  # type: ignore[arg-type]
    assert score.value is not None
    assert score.value > 0.99
    assert score.metadata["n_tokens"] == 3
    assert math.isclose(score.metadata["mean_neg_logprob"], 0.01, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_low_confidence_logprobs() -> None:
    scorer_fn = token_logprob_uncertainty()
    # log p = -2 → p ≈ 0.135; sustained = uncertain.
    score = await scorer_fn(_state([-2.0, -2.0, -2.0]), _StubTarget())  # type: ignore[arg-type]
    assert score.value is not None
    assert 0.3 < score.value < 0.4
    assert math.isclose(score.metadata["mean_neg_logprob"], 2.0, abs_tol=1e-6)


@pytest.mark.asyncio
async def test_filters_non_finite_logprobs() -> None:
    """A -inf logprob (provider rounding artifact) shouldn't poison the mean."""
    scorer_fn = token_logprob_uncertainty()
    score = await scorer_fn(
        _state([-0.5, float("-inf"), -0.5]), _StubTarget()  # type: ignore[arg-type]
    )
    assert score.value is not None
    # Mean is over the two finite tokens only.
    assert math.isclose(score.metadata["mean_neg_logprob"], 0.5, abs_tol=1e-6)
    assert score.metadata["n_tokens"] == 2
