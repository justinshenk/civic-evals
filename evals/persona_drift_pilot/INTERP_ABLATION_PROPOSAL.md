# Interp ablation proposal — "is axis-1 internally null, or output-suppressed?"

**For:** the interp researcher on the §3 workstream.
**Builds on:** `evals/persona_drift_pilot/` (black-box pilot results) and
Poonia & Jain, "Dissecting Persona-Driven Reasoning in Language Models
via Activation Patching", *Findings of EMNLP 2025*, pp. 24553–24566.
**Estimated cost:** 1 GPU (A100-80GB or single-H100) for ~2 days,
no external API spend.
**Owner:** TBD.

---

## 1. The question this answers

Our pilot found that axis-1 (persona-attribute) drift is **≈ 0** on
flagship closed-weights models — `generic_citizen` vs
`suppression_interested` produced mean |Δstance| of 0.01 across five
election-policy topics. That's a black-box null. The next question is
mechanistic:

> Is the persona-attribute axis null because the model **doesn't encode
> persona for civic stance**, or because it **encodes the persona
> internally but projects to a neutral stance at the output**?

The two cases have very different implications for the §3 paper:

- **Internally null** → flagship safety training has actually removed
  persona-conditioning for civic content. Strong positive finding;
  axis 1 is settled, broaden to other models.
- **Internally active, output-suppressed** → the suppression is a thin
  output-side veneer. Anything that bypasses it (fine-tunes, RAG
  pipelines that reinject context, logit-bias prompting, distillation
  to weaker models) could surface the drift again. That's a
  policy-relevant finding distinct from the headline pilot result.

Poonia & Jain give us a sharp tool for the second hypothesis: they
localize persona-driven reasoning to **early MLP layers** (semantic
processing of persona tokens) and **middle MHA layers** (shaping output
using those enriched representations). If our personas activate the
same circuit, then output-side suppression is the mechanism — the
internal "axis 1" exists.

## 2. Why this is an ablation, not just a probe

A probe says: "this representation is decodable." An ablation says:
"this representation is *load-bearing* — when we knock it out, the
downstream behavior we care about changes." We want the second. The
specific design:

1. Run the model under our `suppression_interested` persona; capture
   activations at the layers Poonia & Jain identify.
2. Run again under the `generic_citizen` baseline persona at the same
   token positions.
3. **Patch** the baseline persona's activations into the
   `suppression_interested` run at the identified layers; measure
   whether the next-token distribution over stance-discriminating
   tokens shifts back toward the baseline.

If patching kills a stance shift that existed in the unpatched
treatment run, the early-MLP / middle-MHA circuit is the carrier. If
there is no stance shift to kill (i.e., closed-API behavior reproduces
on open weights too), we have a clean negative for that axis on that
model class.

## 3. Concrete setup

### Model
Start small for iteration speed, then scale:

| stage | model                                            | hardware           | purpose                  |
| ----- | ------------------------------------------------ | ------------------ | ------------------------ |
| 3a    | `meta-llama/Llama-3.1-8B-Instruct`               | 1× 24 GB GPU       | smoke / circuit found?   |
| 3b    | `meta-llama/Llama-3.3-70B-Instruct` (in our suite) | 1× 80 GB GPU       | flagship open-weights    |
| 3c    | `Qwen2.5-72B-Instruct` (optional)                | same               | cross-family generalization |

Closed-API flagships (Haiku 4.5, GPT-4o) are unreachable for this —
we accept that as the trade-off and frame the finding as
"open-weights mechanism; closed-weights behavior matches at the
output". If the circuit is the same across two open families, the
parsimonious read is that the closed flagships likely run the same
mechanism plus output-side suppression.

### Tasks
Reuse the pilot's five interpretive questions verbatim. Two persona
conditions only — `generic_citizen` and `suppression_interested` —
because the pilot already isolated those as the strong contrast.

### Persona injection format
Pilot uses the chat-template `system` message. For activation patching
we need **deterministic token positions** for the persona tokens, so:

- Render the persona as an inline preamble (the same string
  `p3.personas.render(Persona)` produces) at the start of the user
  turn, not in `system`.
- Tokenize once, record the persona token-span as `[start, end)`.
- Patch only activations within that span (and the immediately
  following context — Poonia & Jain show information flows from
  persona tokens forward).

This is a small departure from how the eval runs in production; note
it in the writeup. The trade-off is acceptable: we need positional
control more than we need chat-template fidelity.

### Layers to patch
Per Poonia & Jain, patch in two passes:

1. **Early MLP pass.** Patch the MLP-out activation at the persona
   token positions for layers `[0, L/3)` where `L` is total layer
   count. (Llama-3.1-8B has 32 layers → patch [0, 11). Llama-3.3-70B
   has 80 → patch [0, 27).) This isolates the "semantic processing of
   persona tokens" finding.
2. **Middle MHA pass.** Patch the attention-output activation at the
   final-user-token position for layers `[L/3, 2L/3)`. This isolates
   the "shape the model's output" finding.

A third pass — **head-level localization** within the middle MHA
range — is the EMNLP extension we want to publish. They identified
heads that disproportionately attend to racial/color identities; do
the **same** heads light up for our political-identity persona
(`suppression_interested`), or are there separate political-identity
heads? Per-head activation patching answers this directly.

### Metric
Stance is too coarse for a single forward pass (the pilot showed why).
Use a **token-level stance score** instead:

- Pick the next-token slot immediately after the model's response
  scaffolding lands on a substantive token. (Procedurally: run a few
  unsteered forward passes, find the first position where the model
  emits a clearly stance-bearing token like *support*, *oppose*,
  *evidence*, *strict*, etc.; freeze that position for the ablation.)
- Compute the log-odds of stance-positive vs stance-negative anchor
  tokens at that position (small fixed vocabulary per topic, e.g. for
  voter_id: positive anchors {*support*, *secure*, *integrity*},
  negative {*disenfranchise*, *barriers*, *suppress*}).
- The drift signal is `log P_positive − log P_negative` under each
  condition. Visible internal drift = nonzero gap between clean and
  treatment; load-bearing circuit = patching restores the clean gap.

This metric runs in one forward pass per condition and bypasses both
the stance-judge cost and the output-side hedge-projection that
washed our pilot signal out.

## 4. Hypothesis grid

|                                    | open-weights signal | conclusion                                                                                                                |
| ---------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| treatment ≠ clean in token logits  | yes                 | persona is encoded; check if patching neutralizes                                                                          |
| treatment ≈ clean in token logits  | no                  | open-weights model also doesn't condition on persona; null on closed weights is plausibly mechanism-level, not suppression  |
| patch (early MLP) restores clean   | yes                 | **early-MLP semantic enrichment is load-bearing** for civic-stance persona conditioning — Poonia & Jain's circuit applies |
| patch (early MLP) doesn't restore  | yes                 | the carrier sits elsewhere (later layers? attention?) — pivot to per-layer ablation sweep                                  |
| middle-MHA head ablation localizes | yes                 | named heads carry persona-to-output signal; the EMNLP "racial/color heads" finding extends to political identity heads    |

The two-by-two on the first two rows is the immediate yes/no the §3
paper needs. The bottom three rows are publishable as a single-page
methods extension to the EMNLP paper if the result lands.

## 5. Deliverables (≤ 2 weeks)

- `interp/persona_drift_ablation/` notebook + scripts in this repo:
  - `00_setup.ipynb` — TransformerLens or NNsight hooks on the chosen
    model
  - `01_capture_clean_and_treatment.py` — collect activations across
    layers for the 5×2 task grid
  - `02_patch_and_score.py` — run the patching grid, write
    `results.json` with per-(topic, layer-range, condition) log-odds
  - `03_figure.py` — one figure: log-odds gap vs layer for clean,
    treatment, patched-MLP, patched-MHA
- Markdown writeup: `interp/persona_drift_ablation/FINDINGS.md`,
  whichever cell of the hypothesis grid we land in.
- Updated `/preview/persona-drift-pilot` page with a "Mechanism"
  section that links to the ablation page and summarizes whether the
  pilot's null axis 1 is internal or output-only.

## 6. Open questions for the interp researcher

These are choices I don't have strong priors on; flag if any change
the design:

1. **TransformerLens vs NNsight vs raw HuggingFace hooks.**
   TransformerLens has the cleanest patching API but lags on the
   largest Llama checkpoints; NNsight is newer but supports 70B
   natively. I'd default to NNsight on 70B and TransformerLens on 8B
   for the smoke pass — your call.
2. **Whether to additionally vary the chat-template format**
   (system-message persona vs inline preamble). The pilot uses
   system-message; the ablation needs inline. A single comparison run
   on 8B confirming the two formats give the same black-box stance
   drift would let us claim the ablation generalizes.
3. **Head-level patching budget.** A full per-head sweep over middle
   MHA on 70B is ~26 layers × ~64 heads = ~1660 patches, each one
   forward pass. Roughly a day of GPU at 8B, several days at 70B.
   Worth scoping a coarse-to-fine schedule (whole-layer first, then
   only the layers with strong effects).
4. **Whether to also reproduce the Poonia & Jain racial/color-head
   finding on Llama-3.1/3.3 as a control.** It would strengthen the
   "same circuit family" claim if the racial-identity heads they
   found in their models replicate on ours, but it's outside the
   scope of §3 — flag if you'd want to bundle it or keep separate.

## 7. Why this is worth doing now

The pilot established the black-box axis-1 null. Without the
mechanistic follow-up, that finding is single-paragraph: "models
ignore persona on civic stance." With the follow-up, it becomes a
two-paragraph result: "models ignore persona at the output, but the
internal circuit Poonia & Jain identified [does / does not] still
fire — meaning the suppression [is / is not] removable by
[fine-tunes, distillation, logit-bias prompting]." That's a much
stronger empirical contribution and connects directly to the
existing literature.
