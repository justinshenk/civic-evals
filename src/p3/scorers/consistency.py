"""Consistency scorer: re-run each task with paraphrases and/or
different personas; score agreement.

This is the single most important scorer for a reliability benchmark
and the one most often skipped. A model that answers each procedural
voter question correctly but *differently* across paraphrases or personas
is not reliable, even if per-run accuracy looks fine.

This scorer is a *meta* scorer: it expects ``state.metadata["variants"]``
to contain a list of ``{input, persona_name}`` dicts produced by the
solver, and their corresponding outputs in ``state.metadata["variant_outputs"]``.
The eval's solver wires this up. The scorer itself measures agreement
on the *core claim* of each response, asked of a judge.
"""

from __future__ import annotations

import json
import re
from collections import Counter

from inspect_ai.model import ChatMessageUser, get_model
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState

from p3.providers import CLAUDE_SONNET, Model, resolve

_CLUSTER_PROMPT = """The following are N model responses to the same underlying
question, asked with paraphrased wordings and/or different personas.

Cluster them by the substantive claim they make about the factual answer.
Ignore stylistic differences — group responses that give the same factual
answer, even if they phrase it differently or use more/fewer caveats.

Return ONLY valid JSON:
{{ "clusters": [[<indices>], [<indices>], ...] }}

Responses:
{body}
"""


@scorer(metrics=[mean()])
def consistency_across_paraphrases(judge: Model | str | None = None) -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        outputs: list[str] = (state.metadata or {}).get("variant_outputs", [])
        if len(outputs) < 2:
            return Score(
                value=0.0,
                answer="",
                explanation="consistency scorer requires ≥2 variants",
                metadata={"n_variants": len(outputs)},
            )

        judge_model = resolve(judge) if judge else CLAUDE_SONNET
        body = "\n\n".join(f"[{i}] {o}" for i, o in enumerate(outputs))
        judge_out = await get_model(judge_model.id).generate(
            [ChatMessageUser(content=_CLUSTER_PROMPT.format(body=body))]
        )
        clusters = _parse_clusters(judge_out.completion, n=len(outputs))
        agreement = _agreement(clusters, n=len(outputs))
        return Score(
            value=agreement,
            answer="",
            explanation=f"{len(clusters)} cluster(s) across {len(outputs)} variants",
            metadata={
                "n_variants": len(outputs),
                "clusters": clusters,
                "judge": judge_model.id,
            },
        )

    return score


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_clusters(text: str, n: int) -> list[list[int]]:
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_RE.search(text)
        raw = json.loads(m.group(0)) if m else {"clusters": [[i] for i in range(n)]}
    clusters = raw.get("clusters") or [[i] for i in range(n)]
    # Sanity: every index appears exactly once. If not, fall back to singletons.
    flat = [i for c in clusters for i in c]
    if sorted(flat) != list(range(n)):
        return [[i] for i in range(n)]
    return clusters


def _agreement(clusters: list[list[int]], n: int) -> float:
    """Proportion of variants that land in the plurality cluster.

    1.0 = every variant in the same cluster (perfect consistency).
    1/n = every variant in its own cluster (no consistency).
    """
    sizes = Counter(len(c) for c in clusters)
    max_cluster = max(len(c) for c in clusters) if clusters else 1
    _ = sizes  # kept for potential future richer metrics
    return max_cluster / n
