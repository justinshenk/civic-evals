"""Single source of truth for the Task schema every eval must conform to.

Enforced by CI. A mentee cannot merge an eval whose ``tasks.jsonl`` fails
``Task.model_validate(...)`` on every row.

Two deliberate choices worth calling out:

- ``persona`` is a **separate slot**, not part of ``input``. Baking persona
  into the input string makes persona x task ablation impossible — you
  can't rerun the same task against a different persona if they are
  fused. Evals compose input + persona at runtime.
- Either ``target`` (for programmatic scoring) or ``rubric`` (for
  LLM-judge scoring) must be set, but not both unset.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

Difficulty = Literal["easy", "medium", "hard"]


class TaskMetadata(BaseModel):
    difficulty: Difficulty
    source: str = Field(
        ...,
        min_length=1,
        description="Citation for where the ground truth comes from — URL, document, or statute reference.",
    )
    tags: list[str] = Field(..., min_length=1)
    notes: str | None = None


class PersonaSlot(BaseModel):
    """A persona reference attached to a task.

    Either name a canonical persona from ``p3.personas.canonical`` or
    supply an inline attribute dict. Leaving this unset means the task
    runs without a persona prefix (the default, generic-citizen baseline).
    """

    name: str | None = None
    attributes: dict[str, str | None] | None = None

    @model_validator(mode="after")
    def _one_of(self) -> PersonaSlot:
        if self.name and self.attributes:
            raise ValueError("Set either persona.name OR persona.attributes, not both.")
        return self


class Task(BaseModel):
    id: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    subdomain: str = Field(..., min_length=1)
    input: str = Field(..., min_length=1)
    target: str | list[str] | None = None
    rubric: str | None = None
    persona: PersonaSlot | None = None
    metadata: TaskMetadata

    @model_validator(mode="after")
    def _target_or_rubric(self) -> Task:
        if self.target is None and self.rubric is None:
            raise ValueError(f"Task {self.id!r}: must set either target or rubric.")
        return self

    @model_validator(mode="after")
    def _persona_not_in_input(self) -> Task:
        lowered = self.input.lower()
        # A cheap guard: mentees sometimes smuggle persona into input
        # with phrases like "As a first-time voter, ...". Real enforcement
        # happens in CI review, but catch the obvious cases.
        smells = ("as a first-time voter", "i am a journalist", "i'm an election worker")
        for smell in smells:
            if smell in lowered:
                raise ValueError(
                    f"Task {self.id!r}: persona appears to be embedded in input "
                    f"({smell!r}). Move it to the persona slot so persona x task "
                    "ablations remain possible."
                )
        return self


def load_tasks(path: str | Path) -> list[Task]:
    """Parse a ``tasks.jsonl`` file. Raises on the first invalid row."""
    tasks: list[Task] = []
    for i, row in enumerate(_iter_jsonl(Path(path)), start=1):
        try:
            tasks.append(Task.model_validate(row))
        except ValidationError as e:
            raise ValueError(f"{path}:{i} — {e}") from e
    return tasks


def _iter_jsonl(path: Path) -> Iterator[dict]:
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            yield json.loads(line)
