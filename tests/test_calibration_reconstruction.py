"""Reconstructed point_score must match the live fermi scorer.

When ``sub_scores.point_score`` isn't available (historical logs run
under earlier scorer versions), the rollup falls back to deriving it
from raw (truth, estimate). The earlier reconstruction stopped at the
linear branch and clamped any rel > 1.0 to 0, while the live scorer
applies an exponential-decay tail. That mismatch makes calibration
AUROC over historical logs disagree with re-scored logs without the
data actually being different.
"""

from __future__ import annotations

import math

import pytest

from analysis.rollup import _reconstruct_point_score
from p3.scorers.fermi import _point_score


@pytest.mark.parametrize(
    ("truth", "estimate"),
    [
        # Within ±10%: full credit.
        (100.0, 100.0),
        (100.0, 105.0),
        # Linear decay range (rel ∈ [0.10, 1.0]).
        (100.0, 50.0),
        (100.0, 200.0),  # exactly rel=1.0
        # Exponential decay range (rel > 1.0): the case the bug missed.
        (100.0, 250.0),  # rel=1.5
        (100.0, 500.0),  # rel=4.0
        (100.0, 0.0),    # rel=1.0 boundary (caught by linear branch)
        # truth=0 edge cases.
        (0.0, 0.0),
        (0.0, 1.0),
        # Negative truth.
        (-100.0, -100.0),
        (-100.0, -90.0),
    ],
)
def test_reconstruction_matches_live_scorer(truth: float, estimate: float) -> None:
    expected = _point_score(estimate, truth)
    actual = _reconstruct_point_score(truth, estimate)
    assert math.isclose(actual, expected, abs_tol=1e-9), (
        f"truth={truth} est={estimate}: reconstruction returned {actual}, "
        f"live scorer returned {expected}"
    )


def test_exp_decay_branch_is_actually_exercised() -> None:
    """Catch a regression where the bug was reintroduced as 'just clamp to 0'."""
    # rel=1.5 → exp(-0.5) ≈ 0.607, NOT 0
    score = _reconstruct_point_score(truth=100.0, estimate=250.0)
    assert score > 0.5, (
        "Reconstruction collapsed the exponential tail back to zero — the "
        "regression is back."
    )
