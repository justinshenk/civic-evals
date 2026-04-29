"""local_government_estimation — Fermi at local civic scale."""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import chain, generate, system_message

from p3.lib import load_samples
from p3.scorers import fermi_calibration

HERE = Path(__file__).parent

_FORMAT_DIRECTIVE = """You will be asked numeric questions about US local government.

End your response with this exact format on the last line:

    ESTIMATE: <number>, CI80: <low>-<high>

The CI80 is your 80% confidence interval. For exact-answer questions,
set the interval tight. For estimation questions, set it wide enough
that you would be calibrated. Numbers can be plain (4500), suffixed
(4.5k), or scientific (4.5e3).
"""


@task
def local_government_estimation() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=chain(system_message(_FORMAT_DIRECTIVE), generate()),
        scorer=fermi_calibration(),
    )
