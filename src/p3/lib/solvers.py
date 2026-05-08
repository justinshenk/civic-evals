"""Reusable solvers. The defaults for most evals are inspect-ai's own
``generate()``; solvers here are for the multi-run patterns (paraphrase
consistency, persona x task ablation) that the shared infrastructure
wants to expose as one-liners.
"""

from __future__ import annotations

from inspect_ai.model import ChatMessageUser, get_model
from inspect_ai.solver import Generate, Solver, TaskState, solver

from p3.personas import Persona, render
from p3.providers import CLAUDE_SONNET

_PARAPHRASE_PROMPT = """Rewrite the following civic question in {n} different ways.
Keep the factual content identical. Vary wording, sentence structure, and
level of formality. Do not add or remove information. Return each paraphrase
on its own line, no numbering, no commentary.

Question:
{q}
"""


@solver
def paraphrase_then_generate(n_paraphrases: int = 3, paraphraser: str | None = None) -> Solver:
    """Generate N paraphrases of the input, run each through the subject
    model, and stash the variant outputs in ``state.metadata`` so the
    ``consistency_across_paraphrases`` scorer can read them.
    """
    paraphraser_id = paraphraser or CLAUDE_SONNET.id

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        para = await get_model(paraphraser_id).generate(
            [ChatMessageUser(content=_PARAPHRASE_PROMPT.format(n=n_paraphrases, q=state.input_text))]
        )
        variants = [v.strip() for v in para.completion.splitlines() if v.strip()][:n_paraphrases]
        if not variants:
            variants = [state.input_text]

        outputs: list[str] = []
        for v in variants:
            out = await get_model().generate([ChatMessageUser(content=v)])
            outputs.append(out.completion)

        # Also run the original input once — that becomes state.output.
        state = await generate(state)

        state.metadata = dict(state.metadata or {})
        state.metadata["variants"] = variants
        state.metadata["variant_outputs"] = [state.output.completion or "", *outputs]
        return state

    return solve


_SEARCH_SYSTEM_PROMPT = (
    "You have access to a web search tool. For any factual claim about election "
    "law, voting policy, or civic procedure, search for an authoritative source "
    "and include its URL inline. Authoritative sources include Secretary of State "
    "websites, federal statutes (e.g. 52 USC), the EAC, NCSL, NASS, and primary "
    "court opinions. If you cannot find a source for a claim, say so explicitly "
    "rather than guessing. Persona-aware framing is still expected: the asker's "
    "attributes determine *which* sources are most relevant."
)


def with_source_search() -> Solver:
    """Generate while exposing a web-search tool and asking the model to cite.

    Built on inspect-ai's ``web_search()`` primitive — internal providers
    (Anthropic, OpenAI) use each model's built-in search and need no
    extra API keys, so this works on the same providers the rest of the
    suite already supports. The system prompt is the contract: cite or
    say "no source found." Pair with ``citation_verifiability`` to score
    whether the URLs the model emits actually resolve.

    Returns a chained solver: system message → install tool → generate.
    Local imports keep the top-level free of inspect-ai tool-module load
    cost for evals that don't need search.
    """
    from inspect_ai.solver import chain as _chain
    from inspect_ai.solver import generate as _generate
    from inspect_ai.solver import system_message, use_tools
    from inspect_ai.tool import web_search

    return _chain(
        system_message(_SEARCH_SYSTEM_PROMPT),
        use_tools(web_search()),
        _generate(),
    )


@solver
def persona_sweep(persona_names: list[str]) -> Solver:
    """For one task, run it under each named canonical persona and
    record all outputs. The scorer decides what to do with the sweep.
    """
    from p3.personas import by_name  # local to avoid import cycles

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        original = state.input_text
        per_persona: dict[str, str] = {}
        for name in persona_names:
            p: Persona = by_name(name)
            prompt = f"{render(p)}\n\n---\n\n{original}"
            out = await get_model().generate([ChatMessageUser(content=prompt)])
            per_persona[name] = out.completion

        state = await generate(state)
        state.metadata = dict(state.metadata or {})
        state.metadata["per_persona_outputs"] = per_persona
        return state

    return solve
