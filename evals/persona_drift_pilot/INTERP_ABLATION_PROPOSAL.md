# Interp ablation plan — load-bearing circuits for civic-stance drift

**For:** the interp researcher on the §3 workstream.
**Builds on:** `evals/persona_drift_pilot/` (black-box pilot) and
Poonia & Jain, "Dissecting Persona-Driven Reasoning in Language
Models via Activation Patching", *Findings of EMNLP 2025*
([2025.findings-emnlp.1335](https://aclanthology.org/2025.findings-emnlp.1335/)).
**Owner:** TBD.

> v2 — pivots the headline target from axis 1 (persona-attribute, null
> in the pilot) to **axis 3 (false_prior, the only axis with signal)**;
> adds a step-zero logit gate before any hooks; adds anchor-vocabulary
> validation and matched-control patching; revises the cost estimate;
> drops the "closed flagships likely run the same mechanism" framing.
> §15 lists the target figures and target talks the work is being
> shaped toward.

## 1. The questions

The pilot's three axes on Claude Haiku 4.5:

| axis                   | mean &#124;Δstance&#124; | notes                                                           |
| ---------------------- | ------------------------ | --------------------------------------------------------------- |
| persona_attribute      | 0.01                     | flat null                                                       |
| sycophantic_pressure   | 0.02                     | flat null                                                       |
| **false_prior**        | **0.15**                 | **−0.57 on voter_id (auto-refute); ≈0 on the other 4 (silent fold)** |

Two mechanistic questions follow, in priority order.

**Primary (worth the GPU budget).** For false_prior, what circuit
carries the drift? The voter_id case where the model auto-refutes the
false premise and the four cases where the model silently folds the
premise into a hedge should activate different internal pathways.
Locating those gives both a publishable interp result and a concrete
lever for the §3 paper ("the contamination is mediated by [X];
interventions that suppress [X] would block the silent-fold mode
without blocking the auto-refute mode").

**Secondary (smoke check on the same infra).** For the null axes
(persona, pressure), is the null internal — model truly doesn't
encode the condition — or output-suppressed — encoded but projected
to a neutral hedge by a late stage? Cheaper to answer; runs on the
same model and rigging.

## 2. The handle

Poonia & Jain (EMNLP'25 Findings) localize persona-driven reasoning
in language models to:

- **Early MLP layers** — semantic processing of persona tokens.
- **Middle MHA layers** — output shaping using the enriched persona
  representations.
- **Specific heads** — they identify heads that disproportionately
  attend to racial / color-coded identities.

We adapt their localization to a different conditional drift
(false_prior) on the same family of methods. The persona axis becomes
a smoke check rather than the headline.

## 3. Step zero — logit gate (no hooks)

Before writing a single patching hook, do the cheapest possible test:
one forward pass per (topic × condition) on Llama-3.1-8B-Instruct
and compare next-token logits.

For each topic × condition (clean, false_prior, neutral_prior,
persona_treatment, pressure_followup):

1. Run the same conversation under the condition, no model wrapping.
2. Capture the next-token logits at the first substantive response
   position.
3. Compute KL divergence between condition and clean, plus the
   stance log-odds (see §5).
4. Write `results/step_zero_logit_gate.json`.

**Gate decisions:**

- If **false_prior shows zero logit drift on Llama**, the open-weights
  model doesn't reproduce the Haiku behavior at all and the patching
  exercise has nothing to study. Pivot to Qwen2.5 or OLMo before
  spending more time; if no open-weights model shows the drift, write
  up the negative finding and stop.
- If **persona shows logit drift on Llama** even though the pilot
  output was null on Haiku, that is itself a finding — "open-weights
  conditioning at the representation level, output-side suppression
  is the difference." Worth a paragraph in §3 without doing the rest
  of the patching.

Only proceed past step zero on conditions that pass the gate.

## 4. Anchor vocabulary validation

The stance-log-odds metric (§5) reads from per-topic anchor sets.
These are hand-picked; they need to be validated before any result
depends on them.

Procedure on Llama-3.1-8B:

1. Generate 50 unconditioned responses per topic at default temperature.
2. Score each response with the civic-evals stance judge
   (`p3.scorers.stance_extraction` → GPT-4o).
3. For each anchor token, compute Spearman ρ between
   `log P(anchor) at first-substantive-position` and the judge stance
   score across the 50 responses.
4. Drop anchors with ρ < 0.2; flag topics where the surviving
   per-side vocabulary is < 3 tokens — for those, either author more
   anchors or rely on a different metric.

Write `results/anchor_validation.json` with per-(topic, anchor) ρ and
surviving vocab. Anything downstream that uses the metric reads from
this file and refuses to compute when the surviving vocab is too thin.

## 5. Metric — token-level stance log-odds

For a position's logit vector and validated anchor sets:

```
s(topic, position) = log Σ_{t ∈ pos_anchors} P(t)
                   − log Σ_{t ∈ neg_anchors} P(t)
```

Robustness checks the v1 metric was missing:

- **Position sensitivity.** Compute `s` at three positions:
  first-substantive, fifth-substantive, and the position with maximum
  anchor mass. Headline number is the median across positions; flag
  topics where the three disagree on sign.
- **Bootstrap CIs.** Bootstrap-resample over the 5 topics (and over
  paraphrases of each question once stages 0-3 land) to put CIs on
  per-axis aggregates.
- **Symmetric sanity baseline.** Compute the metric on
  unconditioned-generation responses to neutral-topic prompts ("what
  is the capital of Brazil") with the same anchor vocab. Should be
  ≈ 0; non-zero indicates the anchor set has stance bias built in
  and needs re-authoring.

## 6. Patching design — primary (false_prior circuit)

The v1 design patched persona-token activations only. That confounds
"persona content" with "any change to the residual stream at those
positions." v2 adds a matched control.

Per topic, three conversational conditions:

- **clean** — direct question, no prior turns.
- **false_prior** — false premise + pre-filled assistant ack +
  question. Verbatim from `evals/persona_drift_pilot/gen_tasks.py`.
- **neutral_prior** — *topic-matched but factually neutral* prior
  turn + ack + question. Token length matched to false_prior to
  within ±1 token per turn (sample short paraphrases if needed).

Two patching passes:

| pass | source → dest        | layers           | positions                 | what it isolates                          |
| ---- | -------------------- | ---------------- | ------------------------- | ----------------------------------------- |
| A    | false_prior → clean  | early MLP `[0, L/3)` | prior-turn tokens         | does early-MLP semantic processing carry the false content forward? |
| B    | false_prior → clean  | middle MHA `[L/3, 2L/3)` | final-question tokens     | does middle-MHA shape the final answer using the contaminated context? |

Repeat both passes for **neutral_prior → clean**. The **difference**
between (false → clean) and (neutral → clean) patch effects is what
isolates the *false-content* circuit from the *any-prior-turn-here*
artifact.

If the difference is concentrated in a few layers (likely, per
Poonia & Jain), narrow to those and do per-head ablation as a stretch
(§9).

## 7. Patching design — secondary (persona/pressure smoke)

Only run if step zero (§3) showed Llama produces non-trivial logit
drift for these axes. Otherwise skip and report "Llama black-box
matches Haiku black-box on these axes; no internal evidence either
way."

If logit drift is present, run the same A/B patching grid on:

- persona: `generic_citizen` ↔ `suppression_interested` (text from
  `p3.personas`).
- pressure: replay the pilot's two-turn pressure trace.

Smoke; not the headline.

## 8. Format-equivalence gate (inline preamble vs chat-template system)

The pilot uses chat-template `system`-role persona injection. The
ablation needs inline preamble for deterministic token positions.
Before relying on inline results, validate the two formats give
matching black-box behavior:

- 5 topics × 2 personas × {inline, system} → 20 generations on
  Haiku 4.5 (cheap, via the civic-evals stance judge).
- Per-cell |Δstance(inline) − Δstance(system)| must be ≤ 0.10.

**Gate:** if any cell exceeds 0.10, the ablation is measuring a
different phenomenon than the pilot. Either align (e.g. include the
chat template in the patching prompt and live with a less clean
token-span) or report the format-dependence as itself a finding.

## 9. Model + hardware + revised timeline

Realistic, not optimistic:

| stage | model                          | hardware | wall clock | purpose                              |
| ----- | ------------------------------ | -------- | ---------- | ------------------------------------ |
| 0     | Llama-3.1-8B-Instruct          | 1× 24 GB | 1 hour     | logit gate                            |
| 1     | Llama-3.1-8B-Instruct          | 1× 24 GB | 1 day      | anchor validation + metric tuning     |
| 2     | Llama-3.1-8B-Instruct          | 1× 24 GB | 2 days     | layer-range patching, headline result |
| 3     | Llama-3.3-70B-Instruct         | 1× 80 GB | 2 days     | scale check on the headline           |
| 4*    | Llama-3.3-70B-Instruct         | 1× 80 GB | ~1 week    | per-head sweep middle MHA *(stretch)* |

**Headline result lands at stage 2 (~1 week elapsed including
debugging).** Stages 3-4 are stretch goals. Total wall-clock for the
publishable result is closer to **two weeks** than v1's "~2 days,"
once anchor validation, format gate, and matched-control patching are
included.

No external API spend except for ~$5 on the GPT-4o stance judge in
stages 1 and 8.

## 10. SAE alternative — to consider, not gate on

Sparse-autoencoder feature attribution is the obvious 2026 alternative
to activation patching. It tells you which features in a layer's
residual stream activate differentially between conditions, without
the "patch perturbs the whole residual forward" issue. If a Llama
3.1-8B SAE covering the early-MLP / middle-MHA ranges is available
(check the EleutherAI SAE catalog, NDIF SAEs, the
TransformerLens-Lab releases), run feature attribution alongside
patching on the false_prior condition and compare. Agreement
strengthens the localization claim; disagreement is itself
informative.

If no usable SAE is available for our exact model and layer range,
defer — don't gate on SAE infra.

## 11. What this proposal does NOT claim

- It does **not** establish that Claude Haiku 4.5 or GPT-4o run the
  same circuit. The result is about open-weights Llama-family models.
  Generalization to flagship closed-weights models is a hypothesis to
  flag in the writeup, not a finding to assert.
- The "internally active, output-suppressed" reading remains a
  hypothesis even if it lands cleanly on Llama; it would require
  white-box access to the flagship models to test, which we don't
  have.
- Stage 4 (per-head sweep) is a stretch goal. The headline result
  (false_prior circuit localized to a layer range, matched control
  rules out residual-perturbation artifact) lands without it.

## 12. Deliverables (stages 0–3, ~2 weeks)

- Library: prompts + metrics + hooks + patching primitives.
- Scripts: `step_zero_logit_gate`, `anchor_validation`,
  `inline_system_calibration`, `patch_false_prior`,
  `patch_persona_smoke`.
- `results/` — JSON per script, figure per analysis (see §15 for
  target figure shapes).
- `interp/FINDINGS.md` — running writeup organized by the §3 / §6 / §7
  gates above.
- One paragraph + figure linked from `/preview/persona-drift-pilot`
  once the headline lands.

## 13. Open questions for the interp researcher

1. **TransformerLens vs NNsight.** Default: TLens for 8B (cleaner
   patching API), NNsight for 70B (handles the size). Override if you
   prefer.
2. **Anchor authoring.** The vocab is my best guess. If §4 surfaces
   too many drops, want to re-author together or pivot to a
   learned-probe metric?
3. **SAE inclusion.** Worth doing in parallel with patching if a
   compatible SAE exists, or strictly defer?
4. **Stage 4 head sweep.** Worth the ~1 week of 70B GPU? Headline
   result lands at stage 2 either way; stage 4 is the
   methods-extension lever.
5. **Poonia & Jain racial/color-head replication.** Their finding,
   our model, our prompts — strengthens cross-application claim if it
   replicates. Bundle, or keep as separate work?

## 14. Why v2 vs v1

| concern v1 had             | what v2 changed                                                                                    |
| -------------------------- | -------------------------------------------------------------------------------------------------- |
| chased the null axis       | promoted false_prior (signal-bearing) to headline; persona is smoke                                |
| no logit-gate              | §3 step zero runs first, can abort the whole plan in 1 GPU-hour                                    |
| unvalidated anchor metric  | §4 anchor validation against the stance judge, §5 position sensitivity + bootstrap CIs              |
| confounded patching design | §6 matched-control patching (neutral_prior alongside false_prior) isolates false-content circuit   |
| cross-model overclaim      | §11 explicitly disclaims Haiku/GPT-4o generalization; framing is open-weights-only                 |
| optimistic cost estimate   | §9 timeline is ~2 weeks for the headline, head sweep called out as stretch                         |
| inline-vs-system unflagged | §8 format-equivalence gate before any patching result is trusted                                   |
| no SAE acknowledgment      | §10 mentions SAE feature attribution as the obvious alternative; doesn't gate on it                |

## 15. Target figures and target talks

The work is shaped toward a concrete short paper (NeurIPS workshop or
ICLR Tiny Papers track, ~4 pages) and two presentation slots. Each
target figure below is named, sketched, and tied to which deliverable
it goes into. Author the figure-generator alongside the result it
plots — never compute a number you don't plan to show.

### Target venues

- **Headline paper.** Short paper, ~4 pages — best fits NeurIPS or
  ICLR 2027 workshop tracks on interpretability + safety (BlackboxNLP,
  Mechanistic Interpretability workshop, Socially Responsible LM).
  May 2026 submission window is short; aim August 2026 or workshop
  resubmits later in 2026.
- **Methods extension.** If stage 4 lands cleanly, a separate
  short-paper extending Poonia & Jain's localization to political-
  identity heads on Llama-3.3 → EMNLP 2026 Findings or workshop.
- **Internal team show-and-tell.** First slot after stages 0–1 land
  (~1 week in). 10 minutes, scoped to "does the logit gate fire and
  what does it tell us about the anchor metric."
- **External talk (interp-focused).** Once stage 2 lands. Target
  Alignment Forum cross-post, AI Safety Distill talk, or
  Anthropic / DeepMind safety reading-group invite. 20–30 minutes.

### Figure 1 — pilot recap + the open question (poster + paper §1)

Two-panel from the existing civic-evals pilot figure
(`site/public/preview/persona_drift_pilot.png`) plus a callout:

- Left: the per-axis drift bar chart, unchanged from civic-evals.
- Right: zoom on voter_id × false_prior (Δ = −0.57) with the response
  text annotated where the model auto-refutes.
- Bottom callout: "Open question: is the false_prior circuit the same
  as the persona circuit (Poonia & Jain) or a distinct one?"

**Source:** civic-evals figure + a small panel-builder script. No new
computation.

### Figure 2 — step zero logit gate (paper §3, talk slide 3)

Three-panel small-multiples, one per axis (persona, pressure,
false_prior). Each panel:

- X-axis: topic (5 ticks).
- Y-axis: KL(condition || clean) at the first substantive position
  on Llama-3.1-8B.
- Bars color-coded by sign of Δ stance-log-odds (red = treatment
  positive, blue = treatment negative, grey = below noise floor).
- Annotated noise-floor band from the §5 symmetric sanity baseline.

**The figure is a binary go/no-go signal:** if any bar exceeds the
noise floor, that axis × topic is worth patching. If none do, the
plan aborts at stage 0.

### Figure 3 — anchor validation (paper appendix, talk skip)

Heatmap, rows = anchor token, cols = topic, cell = Spearman ρ with
the GPT-4o stance judge over 50 unconditioned generations. Threshold
line at ρ = 0.2. Bottom row shows surviving vocab count per topic.
Appendix-only; not in the main narrative but reviewers will ask, so
author it once and stop.

### Figure 4 — THE HEADLINE: false_prior circuit (paper §4, talk slide 4, poster centerpiece)

The single most important figure. Per-layer patching effect on
Llama-3.1-8B for the voter_id × false_prior condition:

- X-axis: layer index (0–31 for Llama-3.1-8B).
- Y-axis: stance log-odds after patching (relative to clean baseline =
  0, false_prior baseline marked with a dashed horizontal line).
- Three line series:
  - **false_prior → clean patch** at each layer (the raw circuit
    signal, confounded with residual-perturbation).
  - **neutral_prior → clean patch** at each layer (the control).
  - **DIFFERENCE** = false − neutral, in bold (the isolated
    false-content circuit signal).
- Background bands: Poonia & Jain's early-MLP `[0, L/3)` and
  middle-MHA `[L/3, 2L/3)` regions, lightly shaded.
- Annotation arrows on the peak layers in the difference line.

**This is the figure that decides whether the paper exists.** A
clean peak in the difference line at the Poonia & Jain ranges is the
finding. A flat difference line is the negative result and the
paper pivots to "the false_prior drift is not carried by the same
circuit as persona drift."

### Figure 5 — per-topic generalization (paper §4 continuation)

Small-multiples of Figure 4 across all 5 topics. If the
voter_id-shaped peak appears in all 5, the circuit is general. If it
appears only in voter_id, the auto-refutation mechanism is
topic-specific — itself an interesting finding worth a paragraph.

### Figure 6 — per-head heatmap (stage 4, methods-extension paper)

If stage 4 runs: layer × head heatmap of patching effect within the
middle-MHA range. Highlight (a) heads above the 95th percentile of
effect size, (b) any heads that overlap with Poonia & Jain's
racial/color identity heads if their head indices are recoverable.

### Figure 7 — persona/pressure null vs Llama (paper appendix, talk slide 5)

For the secondary smoke check (§7). One row per non-headline axis:

- X-axis: layer index.
- Y-axis: patching effect.
- Series: full effect, with annotation "no significant peak — null
  axis confirmed on Llama at the representation level" OR "peak at
  layer L despite output-side null — see text."

The interesting cell here is the second one: if Llama shows a
representation-level signal that Haiku's output didn't, that's the
"internally active, output-suppressed" reading the v1 plan wanted to
chase.

### Figure 8 — format-equivalence gate (paper appendix)

Scatter: x-axis Δstance under chat-template-system persona, y-axis
Δstance under inline-preamble persona. Identity line drawn. Points
inside ±0.10 band → format-equivalent. Points outside → the
ablation is measuring something different from the pilot.

### Composite slide deck

The eight figures map onto a clean 8-slide talk (intro, gate, anchor
sanity, **headline**, generalization, head-sweep, secondary axes,
format-gate). Slide 4 (Figure 4) is the only "stop and breathe"
slide; everything else is one figure, one sentence.
