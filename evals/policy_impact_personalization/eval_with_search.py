"""policy_impact_personalization variant with web search + citation scoring.

Same dataset as ``eval.py``; differs only in:

- the solver wraps ``generate()`` with ``web_search()`` and a system prompt
  that asks the model to cite authoritative sources or say "no source
  found" rather than guess
- ``citation_verifiability`` is added to the scorer list so we measure
  whether the URLs the model emits actually resolve

Logged under a distinct task name (``policy_impact_personalization_with_search``)
so the rollup naturally separates it from the zero-shot baseline. Run
this opt-in — it's not part of the weekly refresh-results workflow:

    uv run inspect eval evals/policy_impact_personalization/eval_with_search.py \\
        --model anthropic/claude-haiku-4-5

Pair the resulting log with the zero-shot run to measure the lift (or the
cost) of giving the model live access to civic-information sources.
"""

from pathlib import Path

from inspect_ai import Task, task

from p3.lib import load_samples
from p3.lib.solvers import with_source_search
from p3.scorers import (
    appropriate_refusal,
    citation_verifiability,
    information_density,
    rubric_judge,
)

HERE = Path(__file__).parent


@task
def policy_impact_personalization_with_search() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=with_source_search(),
        scorer=[
            rubric_judge(),
            appropriate_refusal(),
            information_density(),
            citation_verifiability(),
        ],
    )
