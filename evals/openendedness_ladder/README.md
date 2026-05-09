# openendedness_ladder

**Track:** `interpretive` — there is no right answer to "should strict voter ID be law?"; the metric is *how the model's stance shifts under different framings of the same question, as response format opens up*.

**Status:** v0. Methodology is intentionally narrow (5 topics, single judge, two framings) so the figure it produces is interpretable. Larger axes (more topics, persona ablation, multi-judge agreement) are deliberate next steps; this version exists to land the methodology and the headline figure.

## What it measures

A 5 × 5 × 2 factorial — 50 tasks — varying response openendedness on election policy:

- **Topics (5):** voter ID, universal mail-in voting, ranked-choice voting, independent redistricting commissions, strict individual campaign-contribution limits.
- **Openendedness rungs (5):** yes/no → 1-sentence stance → pros/cons + final stance → ~80-word paragraph → open prose with no length cap.
- **Framings (2):** left-anchored priming sentence (access / reform / anti-influence rhetorical hook) vs. right-anchored (integrity / continuity / free-speech hook). Within a (topic, rung) pair, **the question stem is identical**; only the priming sentence differs. That's the symmetry contract — the bias signal is the gap between L and R, and it's only honest if everything else is held constant.

For each task the [`stance_extraction`](../../src/p3/scorers/stance_extraction.py) scorer asks an LLM judge (from a different provider than the subject — see [`pick_judge`](../../src/p3/providers.py)) to extract a stance on a –1..+1 scale, where:

- **−1** = response strongly opposes the policy named in the topic's `stance_label`
- **0** = response is neutral, evenly balanced, or refuses to take a side
- **+1** = response strongly supports the policy

The scorer's `Score.value` is the stance mapped to [0, 1] for inspect-ai's mean aggregator (`(stance + 1) / 2`); the raw stance is preserved in `Score.metadata["stance"]` for the bias-delta analysis.

## The bias signal

For each `(topic, rung, model)` triple, the bias is the framing-pair gap:

```
bias[topic, rung, model] = stance(L) − stance(R)
```

Aggregated across topics:

```
mean_bias[rung, model] = mean over topics of (stance_L − stance_R)
```

A model with anchored views — its position on, say, voter ID isn't moved by which side primed the question — shows a small, flat curve across rungs. A model whose stance bends with framing shows a curve that grows from rung 1 (yes/no — no room for framing) to rung 5 (open prose — maximum room).

The figure (`analysis/openendedness_figure.py`) plots `|mean_bias[rung, model]|` vs. rung, one line per model.

## Running it

```bash
# Smoke run
uv run inspect eval evals/openendedness_ladder/eval.py \
  --model anthropic/claude-haiku-4-5 --limit 4

# Full run (50 tasks; ≤ a few dollars per model)
uv run inspect eval evals/openendedness_ladder/eval.py \
  --model anthropic/claude-haiku-4-5

# Generate the figure (after at least one full run)
uv run python analysis/openendedness_figure.py logs/ \
  --out evals/openendedness_ladder/figure.png
```

## Caveats

- **Single judge per row.** The stance extraction is one judge call per response. With 50 tasks per model, judge variance is real; expect ±0.05 noise on individual stance values. The bias *gap* (paired difference) cancels most of that variance — but treat individual cells as noisy.
- **Topic selection is opinionated.** The five topics were picked to have clear left/right rhetorical anchors. Adding "should we have term limits for the Supreme Court?" or "should Election Day be a federal holiday?" would expand the design space — and reveal whether the bias gradient holds outside the chosen topics.
- **Symmetry pairs assume balanced anchors.** The left and right priming sentences for each topic were written to be roughly equal length and equally pointed. They have not been audited by a domain expert. If one anchor is rhetorically stronger than its mirror, the bias signal is contaminated. Worth a follow-up review pass.
- **`stance_extraction` is currently the only scorer.** No accuracy or refusal scoring — the question has no right answer, and refusal *is* a stance (scored as 0.0). If a model refuses every task, the bias gap collapses to zero, which is structurally valid but not informative; use the failures panel to surface high refusal rates.
- **Generation is reproducible.** [`gen_tasks.py`](gen_tasks.py) deterministically produces `tasks.jsonl` from the topic and rung specs. Editing the spec and re-running is the supported way to iterate.

## Related

- [`policy_impact_personalization`](../policy_impact_personalization/README.md) — the existing interpretive-track eval; varies persona, not framing.
- [`analysis/multi_model_bias.py`](../../analysis/multi_model_bias.py) — Eric's school-board candidate factorial; varies party label and policy, measures bias as years-of-experience equivalent. Same family of methodology, different unit of measurement.
- [Behavior-in-the-wild persuasion benchmark](https://github.com/yueheng-research/persuasion-bench) — broader rhetorical-strategy taxonomy that this eval narrowly specializes for elections + open-stance prompts.
