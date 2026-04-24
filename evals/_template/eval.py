"""Template eval. Copy this folder, then edit this file.

Pick scorers from ``p3.scorers`` based on what your tasks measure:

- ground_truth_match        — for tasks with a ``target`` string/regex
- rubric_judge              — for tasks with a ``rubric``
- appropriate_refusal       — for tasks with ``metadata.refusal_expected``
- consistency_across_paraphrases — expensive; for flagship runs
- citation_verifiability    — for tasks where the model is expected to cite
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate

from p3.lib import load_samples
from p3.scorers import ground_truth_match, rubric_judge

HERE = Path(__file__).parent


@task
def template_eval() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=generate(),
        scorer=[ground_truth_match(mode="substring"), rubric_judge()],
    )
