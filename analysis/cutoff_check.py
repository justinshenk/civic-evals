"""Heuristic: did the model acknowledge training-data staleness or hedge?

Reframes the failure-surfacing report. A confidently-wrong answer with no
caveat is the alarming case; a wrong answer that arrives with "this may
have changed since my training data — verify with your state office" is
the model failing *epistemically responsibly*. If most failures fall in
the second bucket, web search is the right intervention, not retraining.

This is a string-match heuristic, not a scorer. It runs on rows already
classified as failures (see ``rollup.collect_failures``), and only on
no-search evals — search-enabled variants are expected to cite a fresh
URL instead of hedging.

The phrase list is curated to minimize false positives. "It depends" on
its own is *not* a staleness signal; phrases like "policies vary by
state" mean the model named a real source of variation. Both are kept;
generic refusals like "I cannot help" are excluded.
"""

from __future__ import annotations

import re

# Phrases grouped by category, all lowercased. Compiled into a single regex
# at import time so per-row checks are O(text length).
_CUTOFF_PHRASES: tuple[str, ...] = (
    # Explicit cutoff / training-data staleness
    "knowledge cutoff",
    "training cutoff",
    "training data",
    "trained on data",
    "as of my last update",
    "as of my training",
    "as of early 20",  # "as of early 2024" etc.
    "as of mid 20",
    "as of late 20",
    "may not have the most recent",
    "may not have the latest",
    "may not reflect the most recent",
    "may be outdated",
    "may be out of date",
    "could be outdated",
    "could have changed since",
    "may have changed since",
    "policies may have changed",
    "rules may have changed",
    "i don't have access to real-time",
    "no access to real-time",
    "i can't browse",
    "i cannot browse",
    "i cannot access the internet",
    "no access to the internet",
    "current information may differ",
    "for the most current",
    "for the latest",
    "always check the latest",
    # Hedge toward authoritative source
    "secretary of state",
    "state election office",
    "your local election",
    "your state's election",
    "election assistance commission",
    "verify with",
    "confirm with",
    "double-check with",
    "consult your state",
    "consult an attorney",
    "consult a lawyer",
    "i recommend checking",
    "i suggest checking",
    "please check",
    "please verify",
    # Variation hedge (model names a real source of jurisdictional variation)
    "varies by state",
    "varies by jurisdiction",
    "rules vary",
    "rules differ",
    "depends on your state",
    "depends on the state",
    "depends on your jurisdiction",
    "may vary by",
    "differ from state to state",
)


_PATTERN = re.compile("|".join(re.escape(p) for p in _CUTOFF_PHRASES), re.IGNORECASE)


def acknowledged_staleness(text: str) -> bool:
    """True if the response contains any cutoff-awareness or authoritative-source hedge phrase.

    Empty/whitespace-only text returns False. Truncated rollup completions
    (the rollup truncates to 600 chars) are still scanned — the hedge,
    when present, is usually in the first paragraph.
    """
    if not text or not text.strip():
        return False
    return _PATTERN.search(text) is not None


def matched_phrases(text: str, *, limit: int = 3) -> list[str]:
    """Return up to ``limit`` distinct matched phrases for diagnostics.

    Used by the CLI report and the site to show which signal fired so
    reviewers can audit false positives without re-running the regex.
    """
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for m in _PATTERN.finditer(text):
        phrase = m.group(0).lower()
        if phrase in seen:
            continue
        seen.add(phrase)
        out.append(phrase)
        if len(out) >= limit:
            break
    return out


def is_search_eval(eval_name: str | None) -> bool:
    """Search-enabled task variants are expected to cite, not hedge."""
    return bool(eval_name) and eval_name.endswith("_with_search")
