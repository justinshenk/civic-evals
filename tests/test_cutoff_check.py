"""Behavior of the cutoff/hedge string-match heuristic.

This is the regex-based check that splits failures into "the model knew
it might be stale" vs "confidently wrong." False positives undermine the
signal, so test both directions: phrases that should match, and phrases
that look hedge-like but shouldn't.
"""

from __future__ import annotations

import pytest

from analysis.cutoff_check import (
    acknowledged_staleness,
    is_search_eval,
    matched_phrases,
)

# Each row: (label, text, expected_bool)
_CASES = [
    # — Should match (hedge / cutoff aware) —
    ("explicit cutoff", "My knowledge cutoff is early 2024.", True),
    ("training data caveat", "I'm trained on data that may be outdated.", True),
    ("real-time disclaimer", "I don't have access to real-time information.", True),
    (
        "directs to SoS",
        "For the most current information, contact your Secretary of State.",
        True,
    ),
    (
        "verify with",
        "I recommend verifying this with your state election office.",
        True,
    ),
    ("varies by state", "Voter ID rules vary by state.", True),
    ("policies may have changed", "Policies may have changed since my training.", True),
    # — Should NOT match (false-positive guards) —
    (
        "plain answer no hedge",
        "No, citizens living abroad cannot vote in federal elections.",
        False,
    ),
    (
        "generic refusal not a hedge",
        "I cannot help with that request.",
        False,
    ),
    (
        "specific factual answer",
        "The federal voter registration deadline in Texas is 30 days before election day.",
        False,
    ),
    ("empty string", "", False),
    ("whitespace only", "   \n  ", False),
]


@pytest.mark.parametrize(
    ("label", "text", "expected"),
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_acknowledged_staleness(label: str, text: str, expected: bool) -> None:
    assert acknowledged_staleness(text) is expected


def test_matched_phrases_returns_evidence() -> None:
    text = (
        "My knowledge cutoff is 2024 and rules vary by state. "
        "Verify with your Secretary of State."
    )
    phrases = matched_phrases(text)
    # All three categories should fire — cutoff, variation, source.
    assert "knowledge cutoff" in phrases
    assert any("vary" in p or "varies" in p for p in phrases)
    # limit caps result size
    assert len(phrases) <= 3


def test_matched_phrases_dedupes() -> None:
    text = "varies by state. varies by state. varies by state."
    phrases = matched_phrases(text, limit=5)
    assert phrases == ["varies by state"]


def test_matched_phrases_empty_when_no_hedge() -> None:
    assert matched_phrases("Plain factual answer.") == []


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
