"""persona_drift_pilot — three-axis decomposition of conditional civic-LLM drift.

See ``TAXONOMY.md`` for the qualitative spine and ``gen_tasks.py`` for
how the 30 paired tasks are constructed.

Each sample is scored once by ``stance_extraction`` on the model's
final response. Paired drift (baseline ↔ treatment within the same
topic-and-axis pair) is computed offline by
``analysis/persona_drift_rollup.py``.

Three epochs per task at provider default temperature — enough to
spot whether the per-task stance varies across runs without paying for
the full 10-epoch pool the openendedness ladder uses. The pilot's
question is whether axis-level drift signal is real; epochs can grow
once the answer is yes.
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate as _generate  # noqa: F401  (kept for parity with template)

from p3.lib import load_samples
from p3.lib.solvers import multi_turn_drift
from p3.scorers import stance_extraction

HERE = Path(__file__).parent

N_EPOCHS = 3


@task
def persona_drift_pilot() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=multi_turn_drift(),
        scorer=stance_extraction(),
        epochs=N_EPOCHS,
    )
