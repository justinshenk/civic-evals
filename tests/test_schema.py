"""Schema validation — the contract every eval must honor.

Walks ``evals/*/tasks.jsonl`` and asserts:
- parses as valid ``Task`` rows under the pydantic schema
- has at least 5 rows
- each row cites ``metadata.source`` non-empty
- each row has ``metadata.difficulty`` and at least one ``metadata.tags``
- either ``target`` or ``rubric`` is set on every row

CI fails if any eval fails any check. This is what keeps mentee
contributions structurally compatible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from p3.schemas import load_tasks

EVALS_ROOT = Path(__file__).resolve().parent.parent / "evals"


def _eval_dirs() -> list[Path]:
    return sorted(p for p in EVALS_ROOT.iterdir() if p.is_dir() and (p / "tasks.jsonl").exists())


@pytest.mark.parametrize("eval_dir", _eval_dirs(), ids=lambda p: p.name)
def test_tasks_jsonl_valid(eval_dir: Path) -> None:
    tasks = load_tasks(eval_dir / "tasks.jsonl")
    assert len(tasks) >= 5, f"{eval_dir.name}: needs ≥5 tasks, found {len(tasks)}"
    for t in tasks:
        assert t.metadata.source.strip(), f"{t.id}: empty metadata.source"
        assert t.metadata.tags, f"{t.id}: metadata.tags must be non-empty"
        assert (t.target is not None) or (t.rubric is not None), (
            f"{t.id}: must have target or rubric"
        )


def test_task_ids_unique_across_suite() -> None:
    seen: dict[str, str] = {}
    for d in _eval_dirs():
        for t in load_tasks(d / "tasks.jsonl"):
            assert t.id not in seen, (
                f"duplicate task id {t.id!r}: seen in {seen[t.id]}, again in {d.name}"
            )
            seen[t.id] = d.name
