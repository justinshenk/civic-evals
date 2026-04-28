"""Slack summary generator: numeric correctness and shape.

The summary script is a small but load-bearing reporter — every weekly
cron posts its output to a public Slack channel, so silent breakage
(fields renamed, deltas miscomputed, missing-prior path crashing) is
high-cost. These tests exercise:

- per-(eval, provider) mean computation
- delta arrow + magnitude
- categorical-score short-provider tag fits within column
- failure mode payload doesn't reference rollup data
- missing-prior path returns no delta
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from analysis.slack_summary import (
    _eval_provider_means,
    _failure_payload,
    _format_score_cell,
    _short_provider,
    _success_payload,
)


def _stub_rollup(rows: list[dict]) -> dict:
    return {
        "n_rows": len(rows),
        "evals": sorted({r["eval"] for r in rows}),
        "providers": sorted({r["provider"] for r in rows}),
        "rows": rows,
        "external_baselines": [],
        "calibration_stats": [],
    }


def test_means_skip_none_and_string_scores() -> None:
    rows = [
        {"eval": "x", "provider": "p1", "score": 1.0},
        {"eval": "x", "provider": "p1", "score": 0.5},
        {"eval": "x", "provider": "p1", "score": None},
        {"eval": "x", "provider": "p1", "score": "C"},  # categorical, ignored here
        {"eval": "y", "provider": "p2", "score": 0.0},
    ]
    means = _eval_provider_means(_stub_rollup(rows))
    assert means[("x", "p1")] == 0.75
    assert means[("y", "p2")] == 0.0
    # Missing combos are absent rather than 0
    assert ("x", "p2") not in means


def test_score_cell_shows_arrow_when_delta_significant() -> None:
    assert "▲" in _format_score_cell(0.85, 0.80)
    assert "▼" in _format_score_cell(0.70, 0.85)
    # Within ±0.005 = stable
    assert "·" in _format_score_cell(0.800, 0.803)


def test_score_cell_no_prior_means_no_delta() -> None:
    cell = _format_score_cell(0.85, None)
    assert "0.850" in cell
    assert "▲" not in cell and "▼" not in cell


def test_score_cell_missing_current() -> None:
    assert _format_score_cell(None, 0.85) == "—"


def test_short_provider_compaction() -> None:
    s = _short_provider("anthropic/claude-sonnet-4-6")
    assert s.startswith("ant:")
    assert len(s) <= 20
    assert "sonnet-4-6" in s


def test_failure_payload_includes_run_url() -> None:
    p = _failure_payload("https://github.com/x/y/actions/runs/1")
    assert "actions/runs/1" in json.dumps(p)
    assert ":warning:" in json.dumps(p)


def test_failure_payload_safe_without_run_url() -> None:
    p = _failure_payload(None)
    # Must still produce a parseable Slack message
    assert p.get("text")
    assert p.get("blocks")


def test_success_no_prior_emits_no_deltas() -> None:
    rollup = _stub_rollup([
        {"eval": "voting_access", "provider": "anthropic/x", "score": 0.9},
    ])
    payload = _success_payload(rollup, prior=None, run_url=None, commit_sha=None)
    # Use ensure_ascii=False so the unicode arrows would be visible if present,
    # rather than escaped to ▲ / ▼.
    body = json.dumps(payload, ensure_ascii=False)
    assert "▲" not in body and "▼" not in body
    assert "voting_access" in body


def test_success_with_prior_shows_delta() -> None:
    cur = _stub_rollup([
        {"eval": "voting_access", "provider": "anthropic/x", "score": 0.9},
    ])
    prior = _stub_rollup([
        {"eval": "voting_access", "provider": "anthropic/x", "score": 0.7},
    ])
    payload = _success_payload(cur, prior=prior, run_url=None, commit_sha=None)
    body = json.dumps(payload, ensure_ascii=False)
    assert "▲" in body
    # Delta magnitude appears
    assert "0.200" in body


def test_success_handles_empty_rollup() -> None:
    payload = _success_payload(_stub_rollup([]), prior=None, run_url=None, commit_sha=None)
    # Header block always present even when there are no rows
    assert payload["blocks"]
    # No score table block when there's nothing to render
    table_blocks = [b for b in payload["blocks"] if "Mean score" in json.dumps(b)]
    assert table_blocks == []


def test_full_pipeline_against_real_rollup(tmp_path: Path) -> None:
    """End-to-end: read a real rollup.json, generate payload, verify Slack-shaped."""
    real = Path(__file__).resolve().parent.parent / "site" / "public" / "data" / "rollup.json"
    if not real.exists():
        pytest.skip("no real rollup.json available")
    rollup = json.loads(real.read_text())
    payload = _success_payload(rollup, prior=None, run_url=None, commit_sha=None)
    assert isinstance(payload.get("text"), str)
    assert isinstance(payload.get("blocks"), list)
    # Slack rejects payloads >40KB; ours should be well under.
    assert len(json.dumps(payload)) < 40_000
