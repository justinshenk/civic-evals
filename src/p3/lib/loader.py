"""Bridge between ``p3.schemas.Task`` (on-disk JSONL) and inspect-ai
``Sample`` (what solvers and scorers consume).

Every eval loads its tasks through this so the schema-to-sample mapping
is consistent: ``input`` stays in ``Sample.input``, ``target`` or
``rubric`` land where the scorers expect them, and metadata propagates
through so scorers can read ``refusal_expected`` and other per-task
flags.
"""

from __future__ import annotations

import re
from pathlib import Path

from inspect_ai.dataset import Sample

from p3.personas import by_name, render
from p3.personas.attributes import Persona
from p3.schemas import Task, load_tasks

_REFUSAL_EXPECTED_RE = re.compile(
    r"refusal_expected\s*=\s*(refuse|answer|hedge)\b", re.IGNORECASE
)


def task_to_sample(task: Task, attach_persona: bool = True) -> Sample:
    """Convert a schema ``Task`` into an inspect-ai ``Sample``.

    If ``attach_persona`` is True and the task has a persona slot, the
    rendered persona preamble is prepended as a system-style prefix to
    the user input. The solver can alternatively read
    ``sample.metadata['persona']`` and handle it differently (e.g. as a
    separate ``ChatMessageSystem``).
    """
    persona = _resolve_persona(task)

    user_text = task.input
    if attach_persona and persona is not None:
        user_text = f"{render(persona)}\n\n---\n\n{task.input}"

    metadata = {
        "id": task.id,
        "domain": task.domain,
        "subdomain": task.subdomain,
        "difficulty": task.metadata.difficulty,
        "source": task.metadata.source,
        "tags": task.metadata.tags,
        "rubric": task.rubric,
        "persona": persona.as_dict() if persona else None,
    }
    if task.metadata.notes:
        metadata["notes"] = task.metadata.notes
    if task.metadata.extras:
        metadata["extras"] = task.metadata.extras

    refusal_expected = _extract_refusal_expected(task)
    if refusal_expected is not None:
        metadata["refusal_expected"] = refusal_expected

    return Sample(
        id=task.id,
        input=user_text,
        target=task.target or "",
        metadata=metadata,
    )


def load_samples(path: str | Path, attach_persona: bool = True) -> list[Sample]:
    return [task_to_sample(t, attach_persona=attach_persona) for t in load_tasks(path)]


def _extract_refusal_expected(task: Task) -> str | None:
    """Return the expected refusal mode for a task, if declared.

    Prefers structured ``metadata.extras["refusal_expected"]``; falls
    back to parsing ``metadata.notes`` for the legacy
    ``refusal_expected = refuse|answer|hedge`` pattern so existing
    tasks keep working without migration.
    """
    extras = task.metadata.extras or {}
    val = extras.get("refusal_expected")
    if isinstance(val, str) and val.lower() in {"refuse", "answer", "hedge"}:
        return val.lower()
    if task.metadata.notes:
        m = _REFUSAL_EXPECTED_RE.search(task.metadata.notes)
        if m:
            return m.group(1).lower()
    return None


def _resolve_persona(task: Task) -> Persona | None:
    if task.persona is None:
        return None
    if task.persona.name:
        return by_name(task.persona.name)
    if task.persona.attributes:
        return Persona(**task.persona.attributes)  # type: ignore[arg-type]
    return None
