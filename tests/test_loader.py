"""Loader behavior: schema → Sample mapping for fields scorers depend on.

The appropriate_refusal scorer reads ``state.metadata["refusal_expected"]``.
Tasks declare this either as structured ``metadata.extras["refusal_expected"]``
or as a legacy ``refusal_expected = X`` line inside ``metadata.notes``. Both
must surface to the same Sample metadata key, otherwise the scorer is dead.
"""

from __future__ import annotations

from p3.lib.loader import task_to_sample
from p3.schemas import Task


def _task(notes: str | None = None, extras: dict | None = None, **kw) -> Task:
    base = {
        "id": "t-001",
        "domain": "voting_access",
        "subdomain": "registration",
        "input": "?",
        "target": "x",
        "metadata": {
            "difficulty": "easy",
            "source": "test",
            "tags": ["t"],
            "notes": notes,
            "extras": extras,
        },
    }
    base.update(kw)
    return Task.model_validate(base)


def test_refusal_expected_from_notes_refuse() -> None:
    s = task_to_sample(_task(notes="refusal_expected = refuse"))
    assert s.metadata["refusal_expected"] == "refuse"


def test_refusal_expected_from_notes_answer() -> None:
    s = task_to_sample(_task(notes="refusal_expected = answer"))
    assert s.metadata["refusal_expected"] == "answer"


def test_refusal_expected_from_notes_hedge() -> None:
    s = task_to_sample(_task(notes="refusal_expected = hedge"))
    assert s.metadata["refusal_expected"] == "hedge"


def test_refusal_expected_with_trailing_commentary() -> None:
    """Tasks like pip-008 carry extra text after the directive."""
    s = task_to_sample(
        _task(notes="refusal_expected = refuse. The persona is the point of this task.")
    )
    assert s.metadata["refusal_expected"] == "refuse"


def test_refusal_expected_case_insensitive() -> None:
    s = task_to_sample(_task(notes="Refusal_Expected = HEDGE"))
    assert s.metadata["refusal_expected"] == "hedge"


def test_extras_takes_precedence_over_notes() -> None:
    s = task_to_sample(
        _task(
            notes="refusal_expected = answer",
            extras={"refusal_expected": "refuse"},
        )
    )
    assert s.metadata["refusal_expected"] == "refuse"


def test_extras_invalid_value_falls_through_to_notes() -> None:
    s = task_to_sample(
        _task(
            notes="refusal_expected = hedge",
            extras={"refusal_expected": "maybe"},
        )
    )
    assert s.metadata["refusal_expected"] == "hedge"


def test_no_refusal_expected_omits_key() -> None:
    s = task_to_sample(_task(notes="just a note"))
    assert "refusal_expected" not in s.metadata


def test_no_notes_no_extras_omits_key() -> None:
    s = task_to_sample(_task())
    assert "refusal_expected" not in s.metadata


def test_real_eval_tasks_surface_refusal_expected() -> None:
    """Sweep evals/*/tasks.jsonl: any task whose notes contain
    'refusal_expected' must produce a Sample with that key populated.
    Guards against regressions where the loader silently drops it.
    """
    from pathlib import Path

    from p3.schemas import load_tasks

    evals_root = Path(__file__).resolve().parent.parent / "evals"
    checked = 0
    for tasks_jsonl in evals_root.glob("*/tasks.jsonl"):
        for task in load_tasks(tasks_jsonl):
            notes = task.metadata.notes or ""
            extras = task.metadata.extras or {}
            if "refusal_expected" in notes or "refusal_expected" in extras:
                sample = task_to_sample(task)
                assert sample.metadata.get("refusal_expected") in {
                    "refuse",
                    "answer",
                    "hedge",
                }, f"{task.id}: refusal_expected not surfaced (notes={notes!r})"
                checked += 1
    assert checked > 0, "expected at least one real task to declare refusal_expected"
