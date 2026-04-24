"""Bridge between ``p3.schemas.Task`` (on-disk JSONL) and inspect-ai
``Sample`` (what solvers and scorers consume).

Every eval loads its tasks through this so the schema-to-sample mapping
is consistent: ``input`` stays in ``Sample.input``, ``target`` or
``rubric`` land where the scorers expect them, and metadata propagates
through so scorers can read ``refusal_expected`` and other per-task
flags.
"""

from __future__ import annotations

from pathlib import Path

from inspect_ai.dataset import Sample

from p3.personas import by_name, render
from p3.personas.attributes import Persona
from p3.schemas import Task, load_tasks


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

    return Sample(
        id=task.id,
        input=user_text,
        target=task.target or "",
        metadata=metadata,
    )


def load_samples(path: str | Path, attach_persona: bool = True) -> list[Sample]:
    return [task_to_sample(t, attach_persona=attach_persona) for t in load_tasks(path)]


def _resolve_persona(task: Task) -> Persona | None:
    if task.persona is None:
        return None
    if task.persona.name:
        return by_name(task.persona.name)
    if task.persona.attributes:
        return Persona(**task.persona.attributes)  # type: ignore[arg-type]
    return None
