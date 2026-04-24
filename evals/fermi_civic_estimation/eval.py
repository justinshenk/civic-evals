"""fermi_civic_estimation — numeric calibration on civic facts.

Each task expects the model to output a point estimate and 80% CI in a
strict format. The eval prepends a system message describing that
format so individual tasks.jsonl rows stay readable.
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import chain, generate, system_message

from p3.lib import load_samples
from p3.scorers import fermi_calibration

HERE = Path(__file__).parent

_FORMAT_DIRECTIVE = """You will be asked numeric questions about US civic facts.

Some have an exact, knowable answer; others require estimation. Either way,
end your response with this exact format on the last line:

    ESTIMATE: <number>, CI80: <low>-<high>

The CI80 is your 80% confidence interval — the truth should fall inside this
range about 80% of the time across many such questions. For exact-answer
questions, set the interval tight (e.g. CI80: 100-100). For estimation
questions, set it wide enough that you would be calibrated.

Numbers can be plain (158400000), suffixed (158.4M, 334k), or scientific
(1.584e8). Years are plain integers (1971).
"""


@task
def fermi_civic_estimation() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=chain(system_message(_FORMAT_DIRECTIVE), generate()),
        scorer=fermi_calibration(),
    )
