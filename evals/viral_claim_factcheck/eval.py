"""viral_claim_factcheck — rapid-cycle fact checking on circulating civic claims."""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate

from p3.lib import load_samples
from p3.scorers import appropriate_refusal, rubric_judge

HERE = Path(__file__).parent


@task
def viral_claim_factcheck() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=generate(),
        scorer=[rubric_judge(), appropriate_refusal()],
    )
