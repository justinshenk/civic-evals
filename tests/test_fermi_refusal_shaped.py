"""Refusal-shaped fermi outputs are scored as refusals, not as zero.

The ``fermi_civic_estimation`` eval prompts the model for ``ESTIMATE:
<n>, CI80: <l>-<h>``. When the model declines to commit to a number —
either by writing prose ("training cutoff was Oct 2023, FEC has the
data") or by emitting the format with a zero point and zero-width
interval against a non-zero truth — that's a refusal. The previous
scorer rolled both shapes to 0.0 via parse-failure or
``point_score(0, T≠0) = 0`` and a near-zero Winkler interval, which
double-counted calibrated uncertainty as confident error.

These tests pin the new contract:

- Parse failure → 0.5 with ``parse_success=False, refused=True``.
- Structural zero (``est=0, ci=[0,0]``) when truth ≠ 0 → 0.5 with
  ``parse_success=True, refused=True``.
- Genuine confident-zero (estimate 0 against truth 0) still scores
  full credit; refusal heuristic only fires when truth ≠ 0.
- Real numeric answers continue to score the way they always did
  (regression: don't disturb ``point_score`` × ``interval_score``).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from p3.scorers.fermi import fermi_calibration


def _state(completion: str, truth: float | None) -> SimpleNamespace:
    """Minimal TaskState double — the scorer only reads ``state.output.completion``
    and ``state.metadata.extras.truth_value``."""
    extras = {"truth_value": truth} if truth is not None else {}
    return SimpleNamespace(
        output=SimpleNamespace(completion=completion),
        metadata={"extras": extras},
    )


async def _score(completion: str, truth: float | None):
    scorer = fermi_calibration()
    return await scorer(_state(completion, truth), target=None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Parse failure: prose refusal
# --------------------------------------------------------------------------


async def test_prose_refusal_scores_half_not_zero() -> None:
    """fc-017 / fc-019 case: model writes 'I can't answer this — FEC
    has certified results, my training cutoff is Oct 2023.' No
    ``ESTIMATE: <n>`` line emitted. Old scorer: 0.0. New scorer: 0.5."""
    completion = (
        "I can't reliably answer this — the 2024 election had not occurred "
        "by my training cutoff. The FEC publishes certified results."
    )
    s = await _score(completion, truth=226.0)
    assert s.value == 0.5
    assert s.metadata["parse_success"] is False
    assert s.metadata["refused"] is True
    assert s.metadata["truth"] == 226.0
    # Explanation must mention 'refusal' so the failure UI is honest.
    assert "refusal" in s.explanation.lower() or "0.5" in s.explanation


# --------------------------------------------------------------------------
# Structural zero: format emitted but with (0, 0, 0) against non-zero truth
# --------------------------------------------------------------------------


async def test_structural_zero_against_nonzero_truth_is_refusal() -> None:
    """fc-018 / fc-020 case: model emits the format but fills it with
    zeros — '80% confidence the answer is exactly 0 with no width' is
    not a calibrated answer to a positive quantity, it's structural
    refusal. Old scorer: ~0.05 (point_score=0, tiny interval). New: 0.5."""
    completion = "I cannot estimate this. ESTIMATE: 0, CI80: 0-0"
    s = await _score(completion, truth=226.0)
    assert s.value == 0.5
    assert s.metadata["parse_success"] is True
    assert s.metadata["refused"] is True
    assert s.metadata["estimate"] == 0
    assert s.metadata["ci_low"] == 0
    assert s.metadata["ci_high"] == 0


async def test_structural_zero_against_large_truth() -> None:
    """fc-020 case (truth ~7.5e7): same shape, large magnitude — must
    still classify as refusal, not a wild miss."""
    completion = "ESTIMATE: 0, CI80: 0-0"
    s = await _score(completion, truth=7.50176e7)
    assert s.value == 0.5
    assert s.metadata["refused"] is True


async def test_confident_zero_against_zero_truth_still_scores_full() -> None:
    """A question whose true answer is 0 (defunct chamber, impossible
    state count) and a model that confidently emits 0 with zero width
    is *correct*, not refusing. The heuristic must not misclassify it."""
    completion = "The answer is zero. ESTIMATE: 0, CI80: 0-0"
    s = await _score(completion, truth=0.0)
    assert s.value == 1.0
    assert s.metadata["parse_success"] is True
    # No 'refused' marker; this is a genuine answer.
    assert not s.metadata.get("refused")


# --------------------------------------------------------------------------
# Regression: real numeric answers unchanged
# --------------------------------------------------------------------------


async def test_correct_answer_with_tight_interval_scores_high() -> None:
    """100 senators, tight interval that contains. Should score near 1.0."""
    completion = "There are 100 US Senators. ESTIMATE: 100, CI80: 95-105"
    s = await _score(completion, truth=100.0)
    assert s.value > 0.9
    assert s.metadata["parse_success"] is True
    assert not s.metadata.get("refused")


async def test_wrong_numeric_answer_still_penalized() -> None:
    """A model that confidently asserts a wrong number with a tight
    interval missing the truth must still be hammered — refusal credit
    only goes to refusal-shaped outputs, not to wrong-but-committed ones."""
    completion = "ESTIMATE: 50, CI80: 45-55"
    s = await _score(completion, truth=100.0)
    assert s.value < 0.5  # tight miss → low Winkler + bad point score
    assert s.metadata["parse_success"] is True
    assert not s.metadata.get("refused")


async def test_nonzero_estimate_with_zero_width_is_not_refusal() -> None:
    """Model emits ``ESTIMATE: 100, CI80: 100-100`` — overconfident,
    not refusing. Falls through to normal scoring; heuristic should
    not capture it."""
    completion = "ESTIMATE: 100, CI80: 100-100"
    s = await _score(completion, truth=100.0)
    # Truth=estimate, contains, zero width → near-perfect score.
    assert s.value > 0.9
    assert s.metadata["parse_success"] is True
    assert not s.metadata.get("refused")


async def test_zero_estimate_with_nonzero_width_is_not_refusal() -> None:
    """Model emits ``ESTIMATE: 0, CI80: -50 to 50`` — wide hedge
    centered at 0, not a structural zero. The model is *attempting* to
    answer (even badly) and gets the normal scoring path."""
    completion = "ESTIMATE: 0, CI80: -50 to 50"
    s = await _score(completion, truth=100.0)
    assert s.metadata["parse_success"] is True
    assert not s.metadata.get("refused")


# --------------------------------------------------------------------------
# Pre-existing failure modes (no truth metadata) still produce 0.0
# --------------------------------------------------------------------------


async def test_missing_truth_metadata_still_scores_zero() -> None:
    """Truth missing is an authoring bug (eval-data problem), not a
    model refusal. Keep the loud-zero so the failure surfaces as a
    data-quality issue rather than being silently lumped with hedges."""
    s = await _score("ESTIMATE: 100, CI80: 95-105", truth=None)
    assert s.value == 0.0
    assert s.metadata["parse_success"] is False
    assert "no_truth" in (s.metadata.get("reason") or "")


@pytest.mark.parametrize("truth", [-50.0, -1.0])
async def test_negative_truth_with_structural_zero_also_refusal(truth: float) -> None:
    """Trade deficits, deltas, etc. can be negative truths. ``(0, 0, 0)``
    is still refusal-shaped against a non-zero truth, regardless of
    sign."""
    s = await _score("ESTIMATE: 0, CI80: 0-0", truth=truth)
    assert s.value == 0.5
    assert s.metadata["refused"] is True
