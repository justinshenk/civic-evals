"""media_literacy — source reliability + opinion vs fact distinction."""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate

from p3.lib import load_samples
from p3.scorers import rubric_judge

HERE = Path(__file__).parent


@task
def media_literacy() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=generate(),
        scorer=rubric_judge(),
    )
