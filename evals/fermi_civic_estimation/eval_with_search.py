"""fermi_civic_estimation variant with web search + citation scoring.

Same dataset as ``eval.py``; differs only in:

- the solver chains the canonical fermi format directive with the
  search-cite directive, then exposes a ``web_search()`` tool the model
  can call when its training data is too stale to answer
- ``citation_verifiability`` is added to the scorer list so we measure
  whether the URLs the model emits actually resolve

Logged under a distinct task name (``fermi_civic_estimation_with_search``)
so the rollup naturally separates it from the zero-shot baseline.

Motivation: in the zero-shot run, GPT-4o's training cutoff predates the
2024 election, so it correctly refuses on tasks asking about
post-cutoff quantities (fc-017 through fc-020). Those rows now score
0.5 (refusal credit) rather than 0.0 (confident error). The right
intervention isn't retraining; it's giving the model search access.
This variant measures the lift.

Run opt-in (not part of the weekly refresh-results workflow)::

    uv run inspect eval evals/fermi_civic_estimation/eval_with_search.py \\
        --model openai/gpt-4o

Pair the resulting log with the zero-shot run to compute the
search-delta on fermi mean and on the four 2024-election tasks
specifically.
"""

from pathlib import Path

from inspect_ai import Task, task
from inspect_ai.solver import chain, generate, system_message, use_tools
from inspect_ai.tool import web_search

from p3.lib import load_samples
from p3.scorers import citation_verifiability, fermi_calibration

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

_SEARCH_DIRECTIVE = (
    "You have access to a web search tool. Use it for any quantity that "
    "depends on data published after your training cutoff (election results, "
    "current population estimates, recent FEC / Census / EAC reports). "
    "Authoritative sources include Secretary of State websites, federal "
    "agencies (FEC, EAC, Census Bureau), NCSL, NASS, and primary statutory "
    "text. Cite the URL inline. If you cannot find a source, say so "
    "explicitly rather than fabricating an estimate."
)


@task
def fermi_civic_estimation_with_search() -> Task:
    return Task(
        dataset=load_samples(HERE / "tasks.jsonl"),
        solver=chain(
            system_message(_FORMAT_DIRECTIVE),
            system_message(_SEARCH_DIRECTIVE),
            use_tools(web_search()),
            generate(),
        ),
        scorer=[
            fermi_calibration(),
            citation_verifiability(),
        ],
    )
