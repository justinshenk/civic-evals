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
