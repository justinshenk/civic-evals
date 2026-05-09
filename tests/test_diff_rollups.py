"""Diff between two rollup.json snapshots: cell math + markdown shape.

The script's output is meant to be paste-ready in a PR description, so
the contract is "deterministic markdown for a given pair of rollups."
These tests pin:

- cell-mean arithmetic per (eval, scorer, provider)
- threshold filtering elides small moves
- appeared / disappeared cells are listed when sets diverge
- failure-count delta surfaces eval-level changes
- cost section sums usage rows correctly and respects the $0.001 floor
- empty / missing usage block degrades gracefully (no crash, "_No cost…_")
- output is a single trailing newline (snapshot-friendly)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis.diff_rollups import (
    _cell_counts,
    _cell_means,
    _failure_counts,
    _usage_costs,
    render,
)


def _row(eval_: str, scorer: str, provider: str, score: float | None) -> dict:
    return {
        "eval": eval_,
        "scorer": scorer,
        "provider": provider,
        "score": score,
    }


def _rollup(rows: list[dict], **extras) -> dict:
    base = {
        "generated_at": "2026-05-01T00:00:00Z",
        "n_rows": len(rows),
        "evals": sorted({r["eval"] for r in rows}),
        "providers": sorted({r["provider"] for r in rows}),
        "rows": rows,
        "failures": [],
        "usage": [],
    }
    base.update(extras)
    return base


# ---- aggregations ----------------------------------------------------------


def test_cell_means_drops_null_scores() -> None:
    rows = [
        _row("voting_access", "rubric_judge", "anthropic/claude-haiku-4-5", 0.8),
        _row("voting_access", "rubric_judge", "anthropic/claude-haiku-4-5", 1.0),
        _row("voting_access", "rubric_judge", "anthropic/claude-haiku-4-5", None),
    ]
    means = _cell_means(rows)
    key = ("voting_access", "rubric_judge", "anthropic/claude-haiku-4-5")
    assert means[key] == pytest.approx(0.9)


def test_cell_means_empty_on_no_numeric_scores() -> None:
    # All null — the cell is dropped entirely so it shows up as
    # disappeared/appeared rather than as a misleading 0.0.
    rows = [_row("e", "s", "p", None)]
    assert _cell_means(rows) == {}


def test_cell_counts_counts_all_rows() -> None:
    # Counts are independent of score nullity — they say "how many
    # samples did the eval produce" not "how many scored cleanly."
    rows = [_row("e", "s", "p", 1.0), _row("e", "s", "p", None)]
    assert _cell_counts(rows)[("e", "s", "p")] == 2


def test_failure_counts_per_eval() -> None:
    failures = [
        {"eval": "voting_access"},
        {"eval": "voting_access"},
        {"eval": "fermi_civic_estimation"},
    ]
    assert _failure_counts(failures) == {
        "voting_access": 2,
        "fermi_civic_estimation": 1,
    }


def test_usage_costs_sums_per_eval_model() -> None:
    usage = [
        {"eval": "e1", "model": "anthropic/claude-haiku-4-5", "cost_usd": 0.01},
        {"eval": "e1", "model": "anthropic/claude-haiku-4-5", "cost_usd": 0.02},
        {"eval": "e1", "model": "openai/gpt-4o", "cost_usd": 0.05},
        {"eval": "e1", "model": "openai/gpt-4o", "cost_usd": None},
    ]
    costs = _usage_costs(usage)
    assert costs[("e1", "anthropic/claude-haiku-4-5")] == pytest.approx(0.03)
    # None costs are treated as 0 — keeps the cell from disappearing
    # just because one row had unknown pricing.
    assert costs[("e1", "openai/gpt-4o")] == pytest.approx(0.05)


# ---- end-to-end render -----------------------------------------------------


def _render(old: dict, new: dict, threshold: float = 0.02) -> str:
    return render(
        old,
        new,
        old_path=Path("old.json"),
        new_path=Path("new.json"),
        threshold=threshold,
    )


def test_render_threshold_elides_small_moves() -> None:
    old = _rollup([_row("e", "s", "p", 0.80), _row("e", "s", "p", 0.80)])
    # Only a 0.005 shift — well under the 0.02 threshold.
    new = _rollup([_row("e", "s", "p", 0.81), _row("e", "s", "p", 0.80)])
    out = _render(old, new)
    assert "_No cells moved by more than 0.02._" in out
    # And the row should not be in the output table at all.
    assert "0.805" not in out
    assert "0.800" not in out


def test_render_surfaces_meaningful_move() -> None:
    old = _rollup([_row("e", "s", "p", 0.50)])
    new = _rollup([_row("e", "s", "p", 0.80)])
    out = _render(old, new)
    assert "▲" in out
    assert "+0.300" in out
    # n column reflects unchanged sample count.
    assert "| 1 |" in out


def test_render_appeared_and_disappeared_listed() -> None:
    old = _rollup(
        [_row("voting_access", "rubric_judge", "anthropic/claude-haiku-4-5", 0.9)]
    )
    new = _rollup(
        [_row("voting_access", "rubric_judge", "openai/gpt-4o", 0.85)]
    )
    out = _render(old, new)
    assert "Appeared" in out
    assert "openai/gpt-4o" in out
    assert "Disappeared" in out
    assert "anthropic/claude-haiku-4-5" in out


def test_render_failure_section_reports_delta() -> None:
    old = _rollup(
        [_row("e", "s", "p", 1.0)],
        failures=[{"eval": "voting_access"}],
    )
    new = _rollup(
        [_row("e", "s", "p", 1.0)],
        failures=[
            {"eval": "voting_access"},
            {"eval": "voting_access"},
            {"eval": "fermi_civic_estimation"},
        ],
    )
    out = _render(old, new)
    assert "Flagged failures by eval" in out
    assert "+1" in out  # voting_access went 1 → 2
    assert "fermi_civic_estimation" in out


def test_render_cost_section_sums_and_respects_floor() -> None:
    old = _rollup(
        [_row("e", "s", "p", 1.0)],
        usage=[
            {"eval": "e", "model": "anthropic/claude-haiku-4-5", "cost_usd": 0.01},
        ],
    )
    new = _rollup(
        [_row("e", "s", "p", 1.0)],
        usage=[
            {"eval": "e", "model": "anthropic/claude-haiku-4-5", "cost_usd": 0.05},
            # Tiny additional cost on a different model — under $0.001
            # delta shouldn't get its own row.
            {"eval": "e", "model": "openai/gpt-4o", "cost_usd": 0.0005},
        ],
    )
    out = _render(old, new)
    assert "API cost by (eval, model)" in out
    assert "anthropic/claude-haiku-4-5" in out
    # Delta on Haiku was +$0.04 — formatted with the unicode minus only
    # for negative values, plain + for positive.
    assert "+$0.0400" in out
    # GPT-4o entry is absent because its delta is below the floor.
    assert "openai/gpt-4o" not in out


def test_render_no_usage_block_does_not_crash() -> None:
    # Pre-usage-feature rollups didn't carry `usage`. The cost section
    # should degrade to a single explanatory line, not a KeyError.
    old = {"generated_at": "x", "n_rows": 0, "rows": []}
    new = {"generated_at": "y", "n_rows": 0, "rows": []}
    out = _render(old, new)
    assert "No cost cells moved" in out


def test_render_no_cost_flag_skips_section() -> None:
    old = _rollup(
        [_row("e", "s", "p", 1.0)],
        usage=[{"eval": "e", "model": "m", "cost_usd": 0.01}],
    )
    new = _rollup(
        [_row("e", "s", "p", 1.0)],
        usage=[{"eval": "e", "model": "m", "cost_usd": 0.99}],
    )
    out = render(
        old,
        new,
        old_path=Path("o.json"),
        new_path=Path("n.json"),
        threshold=0.02,
        include_cost=False,
    )
    assert "API cost" not in out


def test_render_output_ends_with_single_newline() -> None:
    # Snapshot-friendly: stable trailing whitespace makes diffs in tests
    # and PR bodies less noisy.
    out = _render(_rollup([_row("e", "s", "p", 1.0)]), _rollup([_row("e", "s", "p", 1.0)]))
    assert out.endswith("\n")
    assert not out.endswith("\n\n")


def test_render_header_includes_both_filenames_and_threshold() -> None:
    out = render(
        _rollup([]),
        _rollup([]),
        old_path=Path("rollup-old.json"),
        new_path=Path("rollup-new.json"),
        threshold=0.05,
    )
    assert "`rollup-old.json` → `rollup-new.json`" in out
    assert "≥ 0.05" in out


def test_render_sorts_moves_by_absolute_delta_desc() -> None:
    old = _rollup(
        [
            _row("a", "s", "p", 0.50),
            _row("b", "s", "p", 0.50),
            _row("c", "s", "p", 0.50),
        ]
    )
    new = _rollup(
        [
            _row("a", "s", "p", 0.55),  # +0.05
            _row("b", "s", "p", 0.80),  # +0.30 — biggest, should appear first
            _row("c", "s", "p", 0.40),  # -0.10
        ]
    )
    out = _render(old, new)
    # b's row should appear before a's and c's in the rendered table.
    pos_b = out.find("| b |")
    pos_a = out.find("| a |")
    pos_c = out.find("| c |")
    assert 0 < pos_b < pos_a
    assert 0 < pos_b < pos_c
