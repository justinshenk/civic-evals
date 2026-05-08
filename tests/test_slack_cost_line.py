"""The Slack digest's cost chip: shape, delta, source semantics.

The chip is a one-line piece of meta — it slots into a longer comma-
joined header so it has to stay short and not fail the rest of the
payload when the rollup lacks a usage block (older rollups). Tests
focus on those degradation modes.
"""

from __future__ import annotations

import pytest

from analysis.slack_summary import _format_total_cost, _sum_cost


def _rollup(usage: list[dict] | None) -> dict:
    return {
        "n_rows": 0,
        "evals": [],
        "providers": [],
        "rows": [],
        "external_baselines": [],
        "calibration_stats": [],
        "usage": usage,
    } if usage is not None else {
        "n_rows": 0,
        "evals": [],
        "providers": [],
        "rows": [],
        "external_baselines": [],
        "calibration_stats": [],
    }


def test_no_usage_block_returns_none() -> None:
    """Older rollups predate this field. The chip must absent itself
    cleanly rather than rendering 'None' or '$0' — the meta line just
    drops it."""
    assert _format_total_cost(_rollup(None), None) is None


def test_empty_usage_returns_none() -> None:
    assert _format_total_cost(_rollup([]), None) is None


def test_reported_cost_no_star() -> None:
    rollup = _rollup([{"cost_usd": 1.23, "cost_source": "reported"}])
    chip = _format_total_cost(rollup, None)
    assert chip == "$1.23"


def test_computed_cost_carries_star() -> None:
    rollup = _rollup([{"cost_usd": 0.45, "cost_source": "computed"}])
    chip = _format_total_cost(rollup, None)
    assert chip is not None
    assert chip.endswith("*")
    assert "$0.45" in chip


def test_unknown_row_poisons_total() -> None:
    """If we couldn't price a row, summing past it would silently
    underreport. The chip should refuse to lie — return None."""
    rollup = _rollup(
        [
            {"cost_usd": 0.10, "cost_source": "computed"},
            {"cost_usd": None, "cost_source": "unknown"},
        ]
    )
    assert _format_total_cost(rollup, None) is None


def test_delta_when_significant() -> None:
    cur = _rollup([{"cost_usd": 1.20, "cost_source": "reported"}])
    prv = _rollup([{"cost_usd": 1.00, "cost_source": "reported"}])
    chip = _format_total_cost(cur, prv)
    assert chip is not None
    assert "▲" in chip
    assert "+0.20" in chip


def test_delta_below_threshold_is_suppressed() -> None:
    """Sub-half-cent moves are noise; don't print an arrow."""
    cur = _rollup([{"cost_usd": 1.000, "cost_source": "reported"}])
    prv = _rollup([{"cost_usd": 1.003, "cost_source": "reported"}])
    chip = _format_total_cost(cur, prv)
    assert chip is not None
    assert "▲" not in chip and "▼" not in chip


def test_decrease_uses_down_arrow() -> None:
    cur = _rollup([{"cost_usd": 0.80, "cost_source": "reported"}])
    prv = _rollup([{"cost_usd": 1.00, "cost_source": "reported"}])
    chip = _format_total_cost(cur, prv)
    assert chip is not None
    assert "▼" in chip


def test_sum_cost_aggregates_across_models() -> None:
    rollup = _rollup(
        [
            {"cost_usd": 0.10, "cost_source": "reported"},
            {"cost_usd": 0.20, "cost_source": "computed"},
        ]
    )
    total, estimated = _sum_cost(rollup)
    assert total == pytest.approx(0.30)
    assert estimated  # one row was computed → aggregate is estimated
