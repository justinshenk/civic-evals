"""``metadata.track`` field acceptance + invariants.

Captures the May 2026 research-direction split between *factual* tasks
(verifiable right answer; accuracy/recall is the metric) and
*interpretive* tasks (no single correct answer; persona-conditioned
drift, framing bias, response variance are the metrics that matter).

The field is optional at the schema level so pre-pivot tasks parse
cleanly, but ``test_every_task_in_repo_declares_track`` asserts every
real task in ``evals/*/tasks.jsonl`` has a track set — that's the gate
that prevents regression as new tasks land.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from p3.schemas import Task, load_tasks
from pydantic import ValidationError

_BASE = {
    "id": "x-1",
    "domain": "civics",
    "subdomain": "voting",
    "input": "a fine question",
    "target": "answer",
}


def _meta(**overrides: object) -> dict:
    return {
        "difficulty": "easy",
        "source": "src",
        "tags": ["t"],
        **overrides,
    }


def test_track_optional_omitted_is_fine() -> None:
    # Optional at the schema level — required-by-CI is enforced
    # separately in test_every_task_in_repo_declares_track below.
    Task.model_validate({**_BASE, "metadata": _meta()})


def test_track_optional_explicit_null_is_fine() -> None:
    Task.model_validate({**_BASE, "metadata": _meta(track=None)})


def test_track_factual_accepted() -> None:
    t = Task.model_validate({**_BASE, "metadata": _meta(track="factual")})
    assert t.metadata.track == "factual"


def test_track_interpretive_accepted() -> None:
    t = Task.model_validate({**_BASE, "metadata": _meta(track="interpretive")})
    assert t.metadata.track == "interpretive"


def test_track_unknown_value_rejected() -> None:
    """Free-text values get rejected at load time so a typo can't
    silently classify a task as neither track."""
    for bad in ("unknown", "factual ", "Factual", "interpretive_track", ""):
        with pytest.raises(ValidationError):
            Task.model_validate({**_BASE, "metadata": _meta(track=bad)})


def test_every_task_in_repo_declares_track() -> None:
    """The four currently-merged evals are the floor: every task in
    them must declare a track. Regression guard for new tasks landing
    without the field — pre-pivot tasks were backfilled in the same
    commit that added the schema field.
    """
    evals_root = Path(__file__).resolve().parent.parent / "evals"
    missing: list[str] = []
    checked = 0
    for tasks_jsonl in sorted(evals_root.glob("*/tasks.jsonl")):
        # Skip the boilerplate template eval — it's the starter mentees
        # copy from, not a real eval. The template's own tasks.jsonl
        # demonstrates the field, but pinning it here would couple the
        # exemplar to the production gate.
        if tasks_jsonl.parent.name.startswith("_"):
            continue
        for task in load_tasks(tasks_jsonl):
            checked += 1
            if task.metadata.track is None:
                missing.append(f"{tasks_jsonl.parent.name}/{task.id}")
    assert checked > 0, "expected at least one task in evals/"
    assert not missing, (
        "tasks missing metadata.track (declare 'factual' or 'interpretive' "
        "per the May 2026 research-direction split):\n  " + "\n  ".join(missing)
    )
