"""Bootstrap CI behavior in analysis.rollup.collect_cell_stats.

The site renders the bootstrap interval next to each cell mean. With
small N (often 5–15 after persona expansion), the spread is the more
honest signal than the point estimate alone — but the bootstrap has
to be (a) reproducible across runs, (b) graceful at N<3 (when the
interval is meaningless), and (c) bounded for scores that live in
[0, 1]. These tests pin those invariants.
"""

from __future__ import annotations

import pandas as pd
import pytest

from analysis.rollup import collect_cell_stats


def _row(eval_: str, scorer: str, provider: str, score: float | None) -> dict:
    return {
        "eval": eval_,
        "scorer": scorer,
        "provider": provider,
        "score": score,
    }


def test_returns_empty_on_empty_frame() -> None:
    out = collect_cell_stats(pd.DataFrame())
    assert out == []


def test_drops_null_scores_before_grouping() -> None:
    rows = [
        _row("e", "s", "p", 0.5),
        _row("e", "s", "p", 0.7),
        _row("e", "s", "p", None),
        _row("e", "s", "p", 0.6),
    ]
    out = collect_cell_stats(pd.DataFrame(rows))
    assert len(out) == 1
    assert out[0]["n"] == 3
    assert out[0]["mean"] == pytest.approx(0.6)


def test_n_below_3_emits_null_ci() -> None:
    """At n=1 or n=2 the bootstrap is meaningless. The contract is to
    emit the cell with ci_low/ci_high=null so the UI can show the n
    rather than a fake-precise interval."""
    rows = [_row("e", "s", "p", 1.0), _row("e", "s", "p", 0.0)]
    out = collect_cell_stats(pd.DataFrame(rows))
    assert len(out) == 1
    cell = out[0]
    assert cell["n"] == 2
    assert cell["mean"] == pytest.approx(0.5)
    assert cell["ci_low"] is None
    assert cell["ci_high"] is None


def test_bootstrap_interval_brackets_mean() -> None:
    """For any reasonable distribution the bootstrap percentile CI
    should bracket the empirical mean. Property test rather than
    point test so it survives bootstrap noise."""
    rows = [_row("e", "s", "p", v) for v in [0.7, 0.8, 0.85, 0.9, 0.95, 1.0]]
    out = collect_cell_stats(pd.DataFrame(rows))
    cell = out[0]
    assert cell["ci_low"] is not None
    assert cell["ci_high"] is not None
    assert cell["ci_low"] <= cell["mean"] <= cell["ci_high"]


def test_bootstrap_is_reproducible_across_runs() -> None:
    """The fixed RNG seed in collect_cell_stats means the same input
    must produce the same output on a re-run. Otherwise the rollup.json
    diff for an unchanged eval would show CI-bound noise on every
    regenerate, which would hide real changes."""
    rows = [_row("e", "s", "p", v) for v in [0.5, 0.7, 0.6, 0.8, 0.55, 0.75]]
    a = collect_cell_stats(pd.DataFrame(rows))
    b = collect_cell_stats(pd.DataFrame(rows))
    assert a == b


def test_groups_by_eval_scorer_provider() -> None:
    """Three independent cells; the function groups correctly and
    keeps each cell's mean/CI scoped to its own group."""
    rows = (
        [_row("e1", "rubric", "p1", 1.0)] * 5  # n=5 cell, all 1.0
        + [_row("e1", "rubric", "p2", 0.0)] * 5  # n=5 cell, all 0.0
        + [_row("e2", "ground_truth_match", "p1", 0.5)] * 4
    )
    out = collect_cell_stats(pd.DataFrame(rows))
    assert len(out) == 3
    by_key = {(c["eval"], c["scorer"], c["provider"]): c for c in out}
    assert by_key[("e1", "rubric", "p1")]["mean"] == pytest.approx(1.0)
    assert by_key[("e1", "rubric", "p2")]["mean"] == pytest.approx(0.0)
    assert by_key[("e2", "ground_truth_match", "p1")]["mean"] == pytest.approx(0.5)
    # All three should have non-null CIs since n>=3.
    for c in out:
        assert c["ci_low"] is not None


def test_constant_score_collapses_ci_to_mean() -> None:
    """If every score in a cell is identical, every bootstrap resample
    has the same mean → CI width is exactly 0. Useful guard: a cell
    with all-1.0 scores should not produce ci_low/ci_high outside [0,1]
    due to floating-point drift."""
    rows = [_row("e", "s", "p", 1.0) for _ in range(5)]
    out = collect_cell_stats(pd.DataFrame(rows))
    cell = out[0]
    assert cell["mean"] == pytest.approx(1.0)
    assert cell["ci_low"] == pytest.approx(1.0)
    assert cell["ci_high"] == pytest.approx(1.0)


def test_output_sorted_for_stable_diffs() -> None:
    """Result is sorted by (eval, scorer, provider) so unchanged data
    produces a byte-identical JSON region across rollup regenerations.
    Without this, every rerun would produce a noisy diff in
    rollup.json's cell_stats block."""
    rows = (
        [_row("zeval", "z_scorer", "p1", 0.5)] * 4
        + [_row("aeval", "a_scorer", "p2", 0.7)] * 4
        + [_row("aeval", "z_scorer", "p1", 0.9)] * 4
    )
    out = collect_cell_stats(pd.DataFrame(rows))
    keys = [(c["eval"], c["scorer"], c["provider"]) for c in out]
    assert keys == sorted(keys)
