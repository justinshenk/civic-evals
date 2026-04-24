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

## Scorer selection

Pick from `src/p3/scorers/`:

| Scorer | When to use |
|---|---|
| `ground_truth_match(mode=...)` | Your task has a `target` string (or list/regex) with a single defensible answer. |
| `rubric_judge()` | Your task has a `rubric` describing what a good answer looks like. Scores accuracy, calibrated uncertainty, and refusal appropriateness separately. |
| `appropriate_refusal()` | Your task's correct behavior is refusing, answering, or hedging (set `metadata.notes: refusal_expected=...`). |
| `consistency_across_paraphrases()` | Flagship runs only — pair with `paraphrase_then_generate` solver. Expensive. |
| `citation_verifiability()` | Tasks where the model is expected to cite. Makes live HTTP calls. |

**Do not invent new scorers without discussing on the PR first.** The rollup layer depends on scorers returning the standard shape; a bespoke scorer's numbers won't compare to anyone else's.

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
