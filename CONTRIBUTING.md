# Contributing an eval

Every eval is a folder under `evals/`. You contribute by copying `evals/_template/`, filling it in, and opening a PR. CI validates the schema and smoke-runs your eval against Haiku before anyone reviews it.

## Quickstart

```bash
cp -r evals/_template evals/my_domain
# edit evals/my_domain/{tasks.jsonl, eval.py, README.md}
uv run pytest                                                        # schema + load
uv run inspect eval evals/my_domain/eval.py --model anthropic/claude-haiku-4-5
```

Open a PR when both commands pass locally.

## The schema (`src/p3/schemas.py`)

Every row in your `tasks.jsonl` must parse as a `Task`. Required fields:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique across the whole suite. Prefix with your eval's short name (e.g. `va-001`). |
| `domain` | string | Matches your folder name. |
| `subdomain` | string | Your own subcategory — `registration`, `polling`, `fraud`, etc. |
| `input` | string | The user-facing question. **Do not bake persona into the input string.** |
| `target` OR `rubric` | string | One of the two. `target` for programmatic scoring; `rubric` for LLM-judge. |
| `metadata.difficulty` | `"easy" \| "medium" \| "hard"` | |
| `metadata.source` | string | Real citation — URL, statute, or named document. Empty strings fail CI. |
| `metadata.tags` | list[string] | At least one. |
| `persona` | object (optional) | `{"name": "<canonical>"}` or `{"attributes": {...}}`, never both. |
| `metadata.notes` | string (optional) | Anything a reviewer should know. `refusal_expected = refuse|answer|hedge` goes here if you want the refusal scorer to use it. |
| `metadata.last_verified` | ISO date (optional) | `YYYY-MM-DD` you last checked the source. Tasks with no date or one >12 months old surface as a maintenance signal on the site. |
| `metadata.track` | `"factual" \| "interpretive"` | Required on new tasks (CI gate via `tests/test_track.py`). See *Track* below. |

### Track: factual vs interpretive

Per the May 2026 team direction, civic-evals splits tasks along a research-direction axis:

- **`factual`** — there is a verifiable right answer (statute, agency rule, an explicit numeric truth). Accuracy / recall is the headline metric. The four pre-pivot evals (`voting_access`, `election_integrity`, `fermi_civic_estimation`) are factual.
- **`interpretive`** — the question has no single correct answer (candidate qualifications, policy trade-offs, persona-relative advice). Response variance, persona-conditioned drift, and framing bias are the metrics that matter. `policy_impact_personalization` is interpretive.

Pick the one that fits the *task*, not the eval. An eval can be mixed; the rollup reports the dominant value plus `"mixed"` when both appear. **Do not pick "factual" by reflex** — if the answer depends on persona, jurisdiction, or a value judgment, mark it `interpretive`. The team's research direction is on the interpretive side; mistagging hides interpretive work behind a factual filter on the site.

## Scorer selection

Pick from `src/p3/scorers/`:

| Scorer | When to use |
|---|---|
| `ground_truth_match(mode=...)` | Your task has a `target` string (or list/regex) with a single defensible answer. |
| `rubric_judge()` | Your task has a `rubric` describing what a good answer looks like. Scores accuracy, calibrated uncertainty, and refusal appropriateness separately. |
| `appropriate_refusal()` | Your task's correct behavior is refusing, answering, or hedging (set `metadata.notes: refusal_expected=...`). |
| `fermi_calibration()` | Your task asks for a numeric estimate. The scorer parses `ESTIMATE: <n>, CI80: <l>-<h>` and returns Winkler-based calibration. See `evals/fermi_civic_estimation/`. |
| `token_logprob_uncertainty()` | Non-judge UQ signal: mean negative token logprob. Cheapest of the LM-Polygraph baselines. Requires `generate(logprobs=True)` and an OpenAI subject (Anthropic doesn't expose token logprobs). |

**Experimental scorers** — listed in `p3.scorers.EXPERIMENTAL` but not yet exercised by any eval. Importable but not in `__all__`. A PR adding one of these to a new eval must also add tests for the path it activates:

| Scorer | Status |
|---|---|
| `consistency_across_paraphrases()` | Implementation ready; needs the `paraphrase_then_generate` solver, no eval currently uses it. **Factual track** — clusters responses by claim, so meaningful only when there's a single right answer. |
| `response_variance()` | Implementation ready; same `variant_outputs` contract as `consistency_across_paraphrases` but for **interpretive track**: extracts a -1..+1 stance per variant and scores `1 - std-dev`. Anchored views = high score, persuadable models = low. Requires `metadata.extras.stance_scale` per task. |
| `citation_verifiability()` | Implementation ready; makes live HTTP calls so test setup needs network mocking. |

**Do not invent new scorers without discussing on the PR first.** The rollup layer depends on scorers returning the standard shape; a bespoke scorer's numbers won't compare to anyone else's.

### How our scorers map to the LM-Polygraph taxonomy

The Vashurin et al. benchmark (TACL 2025) groups UQ methods into ~8 families. For mentees designing a new calibration-style eval, here's where ours land — pick the family that matches your task before adding bespoke logic:

| LM-Polygraph family | Our scorer | Notes |
|---|---|---|
| Verbalized / claim-level | `rubric_judge.calibrated_uncertainty` | Judge-mediated; expensive but judges natural-language hedging directly. |
| Logit-based / token-level | `token_logprob_uncertainty` | OpenAI-only at the moment. |
| Sampling-based / consistency | `consistency_across_paraphrases` | Varies the prompt, not the temperature. Factual track. |
| Sampling-based / stance dispersion | `response_variance` | Same paraphrase machinery, but scores std-dev of the model's *stance* on a -1..+1 scale. Interpretive track. |
| Interval forecasts (Winkler) | `fermi_calibration.interval_score` | Specialized: requires the eval to extract an explicit CI from the model. |

If your idea doesn't fit any of these, that's the conversation to start on the PR.

## Personas

Personas are **attribute vectors**, not fixed characters. See `src/p3/personas/canonical.py` for the seven headline personas. Reference them by name: `{"persona": {"name": "first_time_voter"}}`. Attach them in `tasks.jsonl`, not in `input`.

Headline cross-eval reports use the canonical seven. You can add a custom persona with `{"attributes": {...}}` for domain-specific needs, but flag it in your README so reviewers can decide whether to promote it.

## Judge-subject independence

`rubric_judge()` picks a judge provider different from the subject being evaluated (see `p3.providers.pick_judge`). Do not override this without a note in the PR explaining why — judging a model's output with the same model is a known bias.

## Political-lean attribute

Some evals will use `political_lean` as an ablation dimension. If you use it, **pre-register the hypothesis** in your README before running experiments. Post-hoc slicing on political lean is how cherry-picked findings happen.

## Review happens in the Inspect log viewer

Your reviewer will run your eval once and open `inspect view`. They're looking at:

- Do inputs read like real civic questions?
- Do outputs look sensible (not cut-off, not system-prompt-leaked)?
- Do scorer explanations make the grade legible?
- Is the rubric strong enough that a different judge would reach the same score?

Write `tasks.jsonl`, `eval.py`, and `README.md` so all of that is obvious in the log.

## Review checklist (self-check before opening PR)

- [ ] `uv run pytest` passes
- [ ] `uv run inspect eval evals/<me>/eval.py --model anthropic/claude-haiku-4-5` runs to completion
- [ ] `tasks.jsonl` has ≥5 rows
- [ ] Every task cites a real source
- [ ] No persona baked into any `input` string
- [ ] `eval.py` uses only scorers from `p3.scorers`
- [ ] `README.md` covers: what the domain is, sources, known risks, any judgment calls
