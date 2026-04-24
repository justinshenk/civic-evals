"""Ground-truth match scorer: exact, substring, or regex."""

from __future__ import annotations

import re
from typing import Literal

from inspect_ai.scorer import Score, Scorer, Target, accuracy, mean, scorer
from inspect_ai.solver import TaskState

MatchMode = Literal["exact", "substring", "regex"]


@scorer(metrics=[accuracy(), mean()])
def ground_truth_match(mode: MatchMode = "substring", case_sensitive: bool = False) -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion or ""
        targets = _coerce_targets(target)
        matched, matched_on = _match_any(output, targets, mode, case_sensitive)
        return Score(
            value=1.0 if matched else 0.0,
            answer=output,
            explanation=(
                f"{mode} match {'succeeded' if matched else 'failed'}"
                + (f" on {matched_on!r}" if matched_on else "")
            ),
            metadata={"mode": mode, "targets": targets},
        )

    return score


def _coerce_targets(target: Target) -> list[str]:
    raw = target.target
    if isinstance(raw, str):
        return [raw]
    return list(raw)


def _match_any(
    output: str, targets: list[str], mode: MatchMode, case_sensitive: bool
) -> tuple[bool, str | None]:
    haystack = output if case_sensitive else output.lower()
    for t in targets:
        needle = t if case_sensitive else t.lower()
        if mode == "exact" and haystack.strip() == needle.strip():
            return True, t
        if mode == "substring" and needle in haystack:
            return True, t
        if mode == "regex":
            flags = 0 if case_sensitive else re.IGNORECASE
            if re.search(t, output, flags):
                return True, t
    return False, None
