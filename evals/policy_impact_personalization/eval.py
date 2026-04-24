"""policy_impact_personalization — persona-conditioned policy reasoning.

This eval is the on-ramp to the persona-bias research agenda. Each task
carries a populated ``persona`` slot; the ``load_samples`` loader
prepends the rendered persona preamble to the user input. Downstream
ablation experiments (same task, different persona) use
``p3.lib.persona_sweep`` without modifying ``tasks.jsonl``.
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import generate

from p3.lib import load_samples
from p3.scorers import appropriate_refusal, rubric_judge

HERE = Path(__file__).parent


@task
def policy_impact_personalization() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=generate(),
        scorer=[rubric_judge(), appropriate_refusal()],
    )
