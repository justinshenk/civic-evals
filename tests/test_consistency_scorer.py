"""Consistency scorer parser robustness.

The judge call returns prose; ``_parse_clusters`` extracts JSON via a
permissive regex. The earlier implementation could raise
``json.JSONDecodeError`` if the regex matched a brace-delimited
substring that wasn't actually valid JSON — for example if the judge
embedded ``{some explanatory text}`` in its prose. The scorer's
contract is to no-op gracefully; an unhandled raise here would kill
the entire eval run.
"""

from __future__ import annotations

from p3.scorers.consistency import _parse_clusters


def test_valid_json_passes_through() -> None:
    text = '{"clusters": [[0, 1], [2]]}'
    assert _parse_clusters(text, n=3) == [[0, 1], [2]]


def test_prose_wrapped_json_extracted() -> None:
    text = (
        "Sure, the responses cluster as follows:\n"
        '{"clusters": [[0, 1, 2]]}\n'
        "All three give the same factual answer."
    )
    assert _parse_clusters(text, n=3) == [[0, 1, 2]]


def test_malformed_extracted_substring_falls_back_to_singletons() -> None:
    """Regex finds a brace-pair but the contents aren't valid JSON. The
    earlier code raised; the contract is to fall back, not crash."""
    text = "Here are my thoughts: {this isn't JSON at all, just braces} done."
    # Should not raise; should return singleton clusters as a no-op.
    result = _parse_clusters(text, n=3)
    assert result == [[0], [1], [2]]


def test_no_json_at_all_falls_back() -> None:
    text = "I don't know how to answer this."
    assert _parse_clusters(text, n=2) == [[0], [1]]


def test_index_coverage_violation_falls_back() -> None:
    """If clusters reference indices outside [0, n) or skip some, fall back."""
    # Index 5 doesn't exist for n=3.
    text = '{"clusters": [[0, 5]]}'
    assert _parse_clusters(text, n=3) == [[0], [1], [2]]
    # Skipping index 1 for n=3 — partial coverage is also invalid.
    text2 = '{"clusters": [[0], [2]]}'
    assert _parse_clusters(text2, n=3) == [[0], [1], [2]]
