# Civic Evals

**How reliably do AI chatbots answer civic questions?** Civic Evals tests factual accuracy, uncertainty, appropriate refusal, and how answers change with the person asking. Explore the [results dashboard](https://civicevals.org).

Started in the CORDA Democracy Fellowship (2026).

The repo is built on [`inspect-ai`](https://inspect.aisi.org.uk/). Each eval lives in its own folder under `evals/` and contributes tasks to a shared log format. Rollups collect the results while retaining each metric's meaning: quality scores and policy-position scores should be read separately.

## Key results

These May 2026 experiments describe the models and settings in their source reports. They are historical findings, not claims about every current model.

- **Candidate ratings:** all six tested models rated Democratic-typical policy platforms higher, controlling for party label, experience, and rigor. [Six-model study](analysis/multi_model_results.md).
- **Immigration answers shifted with the user's politics:** Claude Haiku 4.5 moved from **+5.16 → −4.38 = 9.54 points** on the −10 to +10 lean scale, with **45** answers per persona. [Scaled persona study](analysis/persona_belief_scaled_results.md).
- **Healthcare replication and fairness instruction:** the healthcare swing was **11.42** points. For immigration, the follow-up reports **9.53 → 4.64 points (51% reduction)** with a fairness instruction. Each number preserves its source report; the two reports give the immigration baseline as 9.54 and 9.53. [Cross-topic and mitigation study](analysis/sycophancy_l0_and_crosstopic_results.md).
- **Candidate-rating mitigation:** a separate Sonnet experiment found an average **~67%** reduction in the user-persona gap across three selected high-gap cells. [Candidate-rating fairness study](analysis/persona_l0_mitigation_results.md).

The October 19, 2026 dashboard refresh completes all seven civic tests on **Claude Sonnet 5.5** (direct Anthropic) and **GPT-6.1 Sol** (OpenRouter), each judged by the other model. Both use high reasoning effort and an 8,192-token output limit. The **862 scored task attempts** retain each test's default repetitions: three epochs for persona drift, ten for open-endedness, and one for the other tests. The 100 external-benchmark scores retain their earlier GPT-4o run and are labeled historical. This suite refresh does not rerun the May research experiments above.

## Quickstart

```bash
uv sync --all-extras
cp -n .env.example .env   # preserve an existing .env; fill in your provider keys
uv run pytest -q         # offline schema, scorer, and module-load checks; no API spend
```

For local cross-vendor judging, configure `ANTHROPIC_API_KEY` and either `OPENAI_API_KEY` or `OPENROUTER_API_KEY`. With only Anthropic and OpenRouter keys, Claude answers are judged by GPT through OpenRouter; OpenAI answers through OpenRouter are judged by Claude directly. Both routes keep the model IDs in the logs. An API error never silently changes the model or billing account.

The following example **makes paid API calls**. Choose a model and budget before running it:

```bash
export P3_ANTHROPIC_JUDGE=anthropic/claude-sonnet-5-5
export P3_OPENAI_JUDGE=openrouter/openai/gpt-6.1-sol
uv run inspect eval evals/voting_access/eval.py \
  --model anthropic/claude-sonnet-5-5 --limit 2 --epochs 1 --log-dir logs/example/
uv run python analysis/usage.py logs/example/
uv run inspect view
```

This example uses Sonnet 5.5 through Anthropic directly and GPT-6.1 Sol through OpenRouter as its judge. Swap `--model` to `openrouter/openai/gpt-6.1-sol` to test GPT with Sonnet judging. The explicit judge overrides select the comparison without changing task prompts or scoring formulas; each must retain the named vendor and have its own route's API key configured. `--limit` bounds sample count, not dollars, and charges include both answers and judges.

The pinned defaults remain available for historical comparisons. GPT-4o is scheduled for API shutdown on January 14, 2027 ([OpenAI notice](https://developers.openai.com/api/docs/deprecations)).

Build a dashboard file from a chosen logs directory without making additional API calls:

```bash
uv run python analysis/rollup.py logs/example/ --skip-staleness-judge \
  --format json -o /tmp/civic-example-rollup.json
```

Without `--skip-staleness-judge`, the rollup can make additional paid Haiku calls to annotate failed answers. The flag leaves those annotations unjudged; it does not change the eval scores. Keep diagnostic logs separate from full runs, and publish only the intended full-run rollup to `site/public/data/rollup.json`.

A [`justfile`](justfile) wraps the common commands so they don't have to be retyped: `just smoke`, `just eval voting_access`, `just rollup`, `just failures`, `just usage`, `just site`. Install with `brew install just` (or `cargo install just`); the raw `uv run …` and `pnpm …` commands remain authoritative — `just` is a convenience layer, never a CI dependency.

## Repo layout

```
src/p3/          shared infrastructure (schema, personas, scorers, providers)
evals/           one folder per eval; mentees copy _template/ to start
analysis/        rollup.py unifies .eval logs into a single long-form dataframe
site/            Next.js App Router dashboard — reads rollup.json, static-exported to GitHub Pages
tests/           offline schema, scorer, reporting, and module-load checks
logs/            .eval outputs (gitignored)
```

## Showcase site

`site/` is a Next.js App Router dashboard that reads `site/public/data/rollup.json` at build time. To run locally:

```bash
cd site
pnpm install
pnpm dev
```

The `refresh-results` GitHub Action runs the eval suite on a weekly schedule (and on `workflow_dispatch`), regenerates `rollup.json`, and commits the update. The `deploy-pages` workflow then rebuilds the static export and republishes it to GitHub Pages automatically.

Repo secrets (set under `Settings → Secrets and variables → Actions`):

- `ANTHROPIC_API_KEY` — required.
- `OPENAI_API_KEY` — optional. When present, every eval also runs against `openai/gpt-4o-2024-08-06`, populating the cross-provider columns on the site. The current workflow uses direct provider keys; local OpenRouter routing does not configure repository secrets.
- `SLACK_WEBHOOK_URL` — optional. When present, the workflow posts a summary to the configured Slack channel after each successful run (per-eval × provider mean table, calibration AUROC, baseline scores, Δ vs. the previous rollup) and a short failure notification when the run dies. No-op when unset, so unconfigured forks don't try to post anywhere.

Deploying to GitHub Pages: the site is a fully static Next.js export, published by the [`deploy-pages`](.github/workflows/deploy-pages.yml) workflow. One-time setup: in **Settings → Pages**, set **Source** to **GitHub Actions**. The workflow runs on pushes to `main` that touch `site/**` (including the weekly `rollup.json` refresh) and on manual dispatch; the published URL is `https://<owner>.github.io/civic-evals/`.

It's served from the `/civic-evals` project subpath via `NEXT_PUBLIC_BASE_PATH` (set in the workflow). For a custom domain or a `<owner>.github.io` user repo, leave that variable unset so the site builds for the root path. Build locally with `pnpm build` (output in `site/out/`).

## Contributing a new eval

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Short version: copy `evals/_template/`, fill in `tasks.jsonl`, `eval.py`, and `README.md`, open a PR. CI validates schemas and loads eval modules offline. A separate smoke job runs a limited Haiku subset when provider keys are available.

## Research agenda

This scaffolding is the foundation for experiments on:

- **Persona-conditioned bias** — varying attributes that shouldn't matter (political lean, profession, language fluency) and measuring whether the model's accuracy, tone, or refusal pattern shifts.
- **Confidence calibration** — does the model's stated confidence track its actual accuracy? Fermi-style estimation under civic framings.
- **Appropriate refusal** — both failure modes matter: confidently inventing voter-ID policy, or refusing to explain a real one.
- **Citation verifiability** — when the model cites, does the source exist and support the claim.

The three reference evals (`voting_access`, `election_integrity`, `policy_impact_personalization`) demonstrate how to wire each of these into the shared infrastructure.

### Persona-drift pilot — early result (May 2026)

`persona_drift_pilot` decomposes conditional drift into three axes (false prior in conversation, persona attribute, sycophantic pressure) over five election topics, scored by `stance_extraction`. First run on `claude-haiku-4-5`, n=30 paired tasks × 3 epochs:

| axis | mean \|drift\| across 5 topics | cells with any drift |
|---|---:|---:|
| `false_prior` | **0.153** | 3 / 5 |
| `persona_attribute` | 0.013 | 1 / 5 |
| `sycophantic_pressure` | 0.020 | 1 / 5 |

Only `false_prior` shows clear signal at this N — almost entirely driven by the voter_id cell (Δ = −0.57 when a false prior is asserted earlier in the conversation). The persona-attribute axis is the headline null: varying who is asking the question barely moves stance on these topics. See `evals/persona_drift_pilot/INTERP_ABLATION_PROPOSAL.md` for the follow-up plan that uses this null as the basis for a mech-interp ablation.

## Methodology notes

The scoring layer is intentionally aligned with the LM-Polygraph benchmark (Vashurin et al., [TACL 2025](https://aclanthology.org/2025.tacl-1.11/)) so results sit alongside published UQ work without translation:

- `fermi_calibration.interval_score` is a relative Winkler interval score — the canonical proper scoring rule for prediction intervals (Winkler 1972; Gneiting & Raftery 2007), which LM-Polygraph aggregates as "interval-based coverage + width."
- `rubric_judge.calibrated_uncertainty` is a verbalized / claim-level UQ signal: one confidence assessment per generated claim, judged by a different-provider LLM.
- `token_logprob_uncertainty` is the cheapest LM-Polygraph baseline — mean negative token logprob. Currently OpenAI-only since Anthropic doesn't expose token logprobs in its API.
- `analysis/rollup.py` reports a per-(eval, provider) **calibration AUROC**, mirroring the LM-Polygraph headline metric specialized to interval forecasts.

`CONTRIBUTING.md` has a more detailed mapping for mentees designing new calibration-style evals.

### Diffing two rollups

PRs that regenerate `site/public/data/rollup.json` produce an unreviewable wall of JSON. `analysis/diff_rollups.py` summarizes the structural delta — mean shifts per `(eval, scorer, provider)` cell, failure-count changes, and per-`(eval, model)` cost movement — as paste-ready markdown:

```bash
just diff old-rollup.json new-rollup.json                  # default threshold |Δmean| ≥ 0.02
uv run python analysis/diff_rollups.py old.json new.json   # equivalent, no `just` required
```

The threshold elides cells inside the noise floor; `--no-cost` skips the API-cost section when the older rollup pre-dates the usage block. The script makes no statistical-significance claim — with N=5–15 per cell, treat the surfaced cells as "places to look" rather than "things that moved."
