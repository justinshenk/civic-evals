"""Print a markdown table of failures pulled from a rollup JSON file.

A failure is any per-row score below the difficulty's "should worry you"
threshold (see ``rollup._FAILURE_THRESHOLDS``). The point of this report is
to make confidently-wrong answers on easy/medium questions visible — a
0.98 mean over an easy binary fact still leaves a small population of
incorrect responses, and those are the ones to inspect.

Usage::

    python analysis/failures.py site/public/data/rollup.json
    python analysis/failures.py rollup.json --limit 20
    python analysis/failures.py rollup.json --eval voting_access

Designed to be paste-ready in a PR description or Slack post.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


def _truncate(text: str, limit: int) -> str:
    """Single-line, length-capped rendering for table cells."""
    text = " ".join(text.split())  # collapse whitespace incl. newlines
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _pipe_safe(text: str) -> str:
    """Markdown table cells can't contain unescaped ``|``."""
    return text.replace("|", "\\|")


_DIFFICULTY_BADGE = {
    "easy": "🟢 easy",
    "medium": "🟡 medium",
    "hard": "🔴 hard",
}


def render(
    failures: list[dict[str, Any]],
    *,
    eval_filter: str | None = None,
    limit: int | None = None,
    completion_chars: int = 220,
) -> str:
    if eval_filter:
        failures = [f for f in failures if f.get("eval") == eval_filter]
    if not failures:
        return "_No failures above the alarm threshold._"

    by_eval: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in failures:
        by_eval[f.get("eval", "?")].append(f)

    out: list[str] = []
    for eval_name in sorted(by_eval.keys()):
        rows = by_eval[eval_name]
        if limit is not None:
            rows = rows[:limit]
        out.append(f"## {eval_name} — {len(by_eval[eval_name])} failures\n")
        out.append(
            "| difficulty | task | persona | provider | scorer | score | judge note | response |"
        )
        out.append("|---|---|---|---|---|---|---|---|")
        for f in rows:
            difficulty = _DIFFICULTY_BADGE.get(f.get("difficulty", ""), f.get("difficulty", "?"))
            score = f.get("score")
            score_s = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
            threshold = f.get("threshold")
            score_cell = f"**{score_s}** (< {threshold:.2f})" if threshold else f"**{score_s}**"
            out.append(
                "| {diff} | `{task}` | `{persona}` | `{provider}` | `{scorer}` | {score} | {note} | {comp} |".format(
                    diff=difficulty,
                    task=_pipe_safe(str(f.get("task_id", "?"))),
                    persona=_pipe_safe(str(f.get("persona", "?"))),
                    provider=_pipe_safe(str(f.get("provider", "?"))),
                    scorer=_pipe_safe(str(f.get("scorer", "?"))),
                    score=score_cell,
                    note=_pipe_safe(_truncate(str(f.get("explanation", "")), 120)),
                    comp=_pipe_safe(_truncate(str(f.get("completion", "")), completion_chars)),
                )
            )
        out.append("")
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("rollup_json", type=Path, help="Path to rollup.json")
    p.add_argument("--eval", dest="eval_filter", default=None,
                   help="Only show failures for this eval name.")
    p.add_argument("--limit", type=int, default=None,
                   help="Max rows per eval section.")
    p.add_argument("--completion-chars", type=int, default=220,
                   help="Character cap on the response cell.")
    args = p.parse_args()

    if not args.rollup_json.exists():
        print(f"Not found: {args.rollup_json}", file=sys.stderr)
        return 1

    payload = json.loads(args.rollup_json.read_text())
    failures = payload.get("failures") or []
    text = render(
        failures,
        eval_filter=args.eval_filter,
        limit=args.limit,
        completion_chars=args.completion_chars,
    )
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
