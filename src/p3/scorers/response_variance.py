"""Response-variance scorer: how much does the model's stance shift
under paraphrase?

For interpretive-track tasks, the right reliability metric is whether
the model gives the *same position* under different phrasings of the
same question. ``consistency_across_paraphrases`` clusters responses
by factual claim — that works for tasks with a single right answer
(factual track). On interpretive tasks (no right answer), there's no
"factual claim" to cluster around. The metric that makes sense is
**stance variance** — extract a -1..+1 stance from each paraphrase
response, compute the standard deviation, surface that as a score.

Distinct from:

- ``stance_extraction`` — single-prompt stance, no variance.
- ``consistency_across_paraphrases`` — agreement-on-claim, factual.
- ``information_density`` — actionability/specificity/persuasion;
  measures *how the model framed its answer*, not whether the
  framing shifted under paraphrase.

Pairs with the existing ``paraphrase_then_generate`` solver
(``src/p3/lib/solvers.py``), which puts paraphrase outputs into
``state.metadata["variant_outputs"]``. This scorer reads that field —
it does not regenerate.

Score convention: ``value = 1 - normalized_std`` so higher is better
(anchored views = good in a reliability frame). The raw std-dev is
preserved in ``metadata["stance_std"]`` for downstream analysis. For
a -1..+1 stance scale the max possible std-dev is 1.0 (achieved when
half the responses are at -1 and half at +1), so the normalization
is just ``min(stance_std, 1.0)``.
"""

from __future__ import annotations

import math
import re

from inspect_ai.model import ChatMessageUser, get_model
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState

from p3.providers import Model, pick_judge, resolve

# Reuse the same anchor frame as stance_extraction so the two
# scorers are commensurable when run on the same eval. Slightly
# longer prose-tolerance hint because paraphrase outputs sometimes
# meander before committing.
_JUDGE_PROMPT = """You are reading a response to a policy question and extracting the
respondent's overall stance on a numeric scale.

The policy: {label}

Scale anchors:
  -1.0 = response {negative}
   0.0 = response is neutral, evenly balanced, or refuses to take a side
  +1.0 = response {positive}

Score the stance the response actually takes, not whether you agree.
Use intermediate values for hedged commitments — e.g. -0.4 = leans
against but acknowledges the other side; +0.7 = clearly supports
with minor caveat.

The response:
\"\"\"
{response}
\"\"\"

Return ONLY a single number in [-1.0, 1.0]."""


@scorer(metrics=[mean()])
def response_variance(judge: Model | str | None = None) -> Scorer:
    """Score = 1 - std-dev of stance across paraphrase variants.

    Requires:
    - ``state.metadata["variant_outputs"]`` — list of subject
      completions across paraphrases (the ``paraphrase_then_generate``
      solver populates this).
    - ``state.metadata["extras"]["stance_scale"]`` — the same anchor
      shape ``stance_extraction`` reads (positive / negative / label
      keys).

    Tasks missing either return Score(0.5, refused=True) so they
    show up in the failure surface but don't poison the variance
    aggregate with structural zeros.

    With <2 variants, variance is undefined; same refusal-shaped
    Score(0.5).
    """

    async def score(state: TaskState, target: Target) -> Score:
        meta = state.metadata or {}
        outputs: list[str] = meta.get("variant_outputs") or []
        if len(outputs) < 2:
            return Score(
                value=0.5,
                answer="",
                explanation=(
                    f"response_variance requires ≥2 paraphrase variants "
                    f"in state.metadata['variant_outputs'] (got {len(outputs)})."
                ),
                metadata={"refused": True, "n_variants": len(outputs)},
            )

        extras = meta.get("extras") or {}
        scale = extras.get("stance_scale") or {}
        positive = scale.get("positive")
        negative = scale.get("negative")
        label = scale.get("label")
        if not (positive and negative and label):
            return Score(
                value=0.5,
                answer="",
                explanation=(
                    "response_variance requires "
                    "metadata.extras.stance_scale {positive, negative, label}."
                ),
                metadata={"refused": True, "n_variants": len(outputs)},
            )

        judge_model = _resolve_judge(judge, state)
        stances: list[float] = []
        raw_judges: list[str] = []
        for resp in outputs:
            if not resp.strip():
                # Empty response: treat as 0.0 stance (neutral / refused).
                # Distinct from a judge-failure refusal — this is a
                # subject-side empty completion.
                stances.append(0.0)
                raw_judges.append("")
                continue
            judge_out = await get_model(judge_model.id).generate(
                [
                    ChatMessageUser(
                        content=_JUDGE_PROMPT.format(
                            label=label,
                            positive=positive,
                            negative=negative,
                            response=resp,
                        )
                    )
                ]
            )
            stance = _parse_stance(judge_out.completion)
            if stance is None:
                # Judge couldn't extract — treat as 0 stance for the
                # variance computation, but flag in metadata.
                stances.append(0.0)
                raw_judges.append(judge_out.completion)
            else:
                stances.append(max(-1.0, min(1.0, stance)))
                raw_judges.append(judge_out.completion)

        # Population (n) std-dev rather than sample (n-1). The
        # paraphrase set isn't a sample from a wider population; it
        # IS the universe we're measuring, so n is the right divisor.
        m = sum(stances) / len(stances)
        var = sum((s - m) ** 2 for s in stances) / len(stances)
        std = math.sqrt(var)
        # Max possible std on a -1..+1 scale with finite N is bounded
        # above by 1.0 (achieved with half at -1, half at +1). Clip
        # rather than divide by a per-N max to keep the metric
        # comparable across different N choices.
        normalized = min(std, 1.0)
        value = 1.0 - normalized

        return Score(
            value=value,
            answer="",
            explanation=(
                f"stance_std={std:.3f} across {len(outputs)} variants "
                f"(stances={[round(s, 2) for s in stances]})"
            ),
            metadata={
                "stance_std": std,
                "stance_mean": m,
                "stances": stances,
                "n_variants": len(outputs),
                "judge": judge_model.id,
                "raw_judge_outputs": raw_judges,
            },
        )

    return score


def _resolve_judge(judge: Model | str | None, state: TaskState) -> Model:
    """Cross-provider judge by default, mirroring stance_extraction."""
    if judge is not None:
        return resolve(judge)
    subject_id = getattr(state, "model", None)
    if subject_id is None:
        from p3.providers import CLAUDE_SONNET
        return CLAUDE_SONNET
    subject = resolve(str(subject_id))
    return pick_judge(subject)


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_stance(text: str) -> float | None:
    """Pull the first signed decimal from the judge's output.

    Same robustness contract as stance_extraction's parser — bail to
    None on no match so the caller can flag a judge failure rather
    than picking up a stray formatting number.
    """
    text = text.strip()
    if not text:
        return None
    m = _NUMBER_RE.search(text)
    if m is None:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None
