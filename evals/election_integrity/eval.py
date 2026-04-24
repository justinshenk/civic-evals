"""election_integrity — misinformation, calibrated refusal, manipulation robustness.

ei-011 and ei-012 form a **symmetry test**: same structural question,
opposite political framing. A reliability failure would be grading one
strictly and the other leniently. The rubric judge sees each task
independently — the symmetry check happens at the rollup layer.
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate

from p3.lib import load_samples
from p3.scorers import appropriate_refusal, ground_truth_match, rubric_judge

HERE = Path(__file__).parent


@task
def election_integrity() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=generate(),
        scorer=[
            rubric_judge(),
            appropriate_refusal(),
            ground_truth_match(mode="substring"),
        ],
    )


# Flagship consistency sweep. Enable for cross-provider headline runs, not CI.
# from p3.lib import paraphrase_then_generate
# from p3.scorers import consistency_across_paraphrases
#
# @task
# def election_integrity_consistency() -> Task:
#     return Task(
#         dataset=load_samples(HERE / "tasks.jsonl"),
#         solver=paraphrase_then_generate(n_paraphrases=3),
#         scorer=[rubric_judge(), consistency_across_paraphrases()],
#     )
