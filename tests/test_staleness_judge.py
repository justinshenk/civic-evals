"""Behavior of the staleness judge — judge-call path with mocked inspect-ai.

The real judge calls Haiku; the tests mock ``get_model`` so CI runs
offline. Coverage targets:

- valid JSON verdicts map cleanly into StalenessVerdict
- prose-wrapped JSON still parses via the regex fallback
- garbage / non-JSON output → null verdict (not a crash, not a default-true)
- ``judge_failures`` skips ``*_with_search`` rows
- cache hit short-circuits the judge call entirely
- missing API key returns null verdicts and never calls the judge
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from analysis.staleness_judge import (
    StalenessVerdict,
    is_search_eval,
    judge_failures,
)


class _StubJudgeOutput:
    def __init__(self, completion: str) -> None:
        self.completion = completion


class _StubJudge:
    """Deterministic responder; records every prompt for assertions."""

    def __init__(self, completion: str) -> None:
        self.completion = completion
        self.received: list[str] = []
        self.calls = 0

    async def generate(self, messages: Any) -> _StubJudgeOutput:
        self.calls += 1
        self.received.append(messages[0].content)
        return _StubJudgeOutput(self.completion)


@pytest.fixture
def patch_judge(monkeypatch: pytest.MonkeyPatch):
    """Returns a setter; also forces the API-key check to pass."""

    def install(completion: str) -> _StubJudge:
        judge = _StubJudge(completion)
        mod = sys.modules["analysis.staleness_judge"]

        # ``get_model`` is imported inside ``_judge_one``; monkeypatch the
        # source module so the lazy import sees the stub.
        from inspect_ai import model as inspect_model
        monkeypatch.setattr(inspect_model, "get_model", lambda _id=None: judge)
        # Always claim a key is present.
        monkeypatch.setattr(mod, "_has_key_for", lambda _id: True)
        return judge

    return install


def _failure(
    *, eval_name: str = "voting_access", task_id: str = "va-005",
    completion: str = "no hedge here",
) -> dict[str, Any]:
    return {
        "eval": eval_name,
        "task_id": task_id,
        "completion": completion,
        "acknowledged_staleness": None,
        "staleness_kind": None,
        "staleness_evidence": None,
    }


def test_acknowledged_cutoff(tmp_path: Path, patch_judge) -> None:
    judge = patch_judge(json.dumps({
        "acknowledged": True,
        "kind": "cutoff",
        "evidence": "knowledge cutoff October 2023",
    }))
    failures = [_failure(completion="As of my knowledge cutoff in October 2023...")]
    judge_failures(failures, cache_path=tmp_path / "cache.json")

    assert failures[0]["acknowledged_staleness"] is True
    assert failures[0]["staleness_kind"] == "cutoff"
    assert "October 2023" in failures[0]["staleness_evidence"]
    assert judge.calls == 1


def test_unacknowledged(tmp_path: Path, patch_judge) -> None:
    patch_judge(json.dumps({
        "acknowledged": False, "kind": "none", "evidence": "",
    }))
    failures = [_failure(completion="No, citizens abroad cannot vote.")]
    judge_failures(failures, cache_path=tmp_path / "cache.json")

    assert failures[0]["acknowledged_staleness"] is False
    assert failures[0]["staleness_kind"] == "none"
    assert failures[0]["staleness_evidence"] is None  # empty -> normalized to None


def test_prose_wrapped_json_parses(tmp_path: Path, patch_judge) -> None:
    patch_judge(
        "Sure, here's my verdict:\n"
        '{"acknowledged": true, "kind": "source", "evidence": "Secretary of State"}\n'
        "Hope this helps."
    )
    failures = [_failure()]
    judge_failures(failures, cache_path=tmp_path / "cache.json")
    assert failures[0]["acknowledged_staleness"] is True
    assert failures[0]["staleness_kind"] == "source"


def test_garbage_judge_output_returns_null(tmp_path: Path, patch_judge) -> None:
    patch_judge("I refuse to grade this and won't return JSON.")
    failures = [_failure()]
    judge_failures(failures, cache_path=tmp_path / "cache.json")
    assert failures[0]["acknowledged_staleness"] is None
    assert failures[0]["staleness_kind"] is None
    assert failures[0]["staleness_evidence"] is None


def test_search_eval_skipped(tmp_path: Path, patch_judge) -> None:
    judge = patch_judge(json.dumps({"acknowledged": True, "kind": "cutoff", "evidence": "x"}))
    failures = [_failure(eval_name="policy_impact_personalization_with_search")]
    judge_failures(failures, cache_path=tmp_path / "cache.json")

    assert failures[0]["acknowledged_staleness"] is None  # not judged
    assert judge.calls == 0  # no API call burned on search-enabled rows


def test_cache_hit_skips_judge(tmp_path: Path, patch_judge) -> None:
    judge = patch_judge(json.dumps({
        "acknowledged": True, "kind": "cutoff", "evidence": "knowledge cutoff",
    }))
    cache_path = tmp_path / "cache.json"
    failures = [_failure(completion="As of October 2023...")]

    judge_failures(failures, cache_path=cache_path)
    assert judge.calls == 1
    assert cache_path.exists()

    # Re-run with fresh failure dicts but the same content — cache should serve.
    failures2 = [_failure(completion="As of October 2023...")]
    judge_failures(failures2, cache_path=cache_path)
    assert judge.calls == 1  # no additional call
    assert failures2[0]["acknowledged_staleness"] is True


def test_null_verdict_not_cached(tmp_path: Path, patch_judge) -> None:
    """A judge crash shouldn't poison the cache — re-runs should retry."""
    patch_judge("garbage")
    cache_path = tmp_path / "cache.json"
    failures = [_failure(completion="some response")]
    judge_failures(failures, cache_path=cache_path)

    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    assert cache == {}, "null verdicts should not be cached"


def test_missing_api_key_skips_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When no key is set, all verdicts are null and no judge call happens."""
    mod = sys.modules["analysis.staleness_judge"]
    monkeypatch.setattr(mod, "_has_key_for", lambda _id: False)

    failures = [_failure()]
    judge_failures(failures, cache_path=tmp_path / "cache.json")
    assert failures[0]["acknowledged_staleness"] is None
    assert failures[0]["staleness_kind"] is None


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("policy_impact_personalization", False),
        ("policy_impact_personalization_with_search", True),
        ("voting_access", False),
        ("", False),
        (None, False),
    ],
)
def test_is_search_eval(name: str | None, expected: bool) -> None:
    assert is_search_eval(name) is expected


def test_verdict_evidence_truncated() -> None:
    """Long quotes get clipped so the rollup JSON stays bounded."""
    from analysis.staleness_judge import _verdict_from_judge

    long = "x" * 500
    v = _verdict_from_judge({
        "acknowledged": True, "kind": "cutoff", "evidence": long,
    })
    assert isinstance(v, StalenessVerdict)
    assert v.evidence is not None
    assert len(v.evidence) <= 200
    assert v.evidence.endswith("…")
