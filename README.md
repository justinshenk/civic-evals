# p3-civic-evals

CORDA P3 research project: **Civic Information Reliability**. A shared evaluation suite for measuring how reliably large language models answer civic questions across providers, personas, and task types.

The repo is built on [`inspect-ai`](https://inspect.aisi.org.uk/). Each eval lives in its own folder under `evals/` and contributes tasks into a single, uniformly-structured log stream. Cross-eval rollups operate on that log stream — so every eval is immediately comparable on accuracy, calibrated uncertainty, appropriate-refusal, consistency, and citation verifiability.

## Quickstart

```bash
uv sync
cp .env.example .env   # fill in ANTHROPIC_API_KEY / OPENAI_API_KEY / TOGETHER_API_KEY
uv run pytest                                                                      # schema + smoke
uv run inspect eval evals/voting_access/eval.py --model anthropic/claude-haiku-4-5
uv run inspect view                                                                # browse logs
uv run python analysis/rollup.py logs/ > rollup.parquet
```

A [`justfile`](justfile) wraps the common commands so they don't have to be retyped: `just smoke`, `just eval voting_access`, `just rollup`, `just failures`, `just usage`, `just site`. Install with `brew install just` (or `cargo install just`); the raw `uv run …` and `pnpm …` commands remain authoritative — `just` is a convenience layer, never a CI dependency.

## Repo layout

```
src/p3/          shared infrastructure (schema, personas, scorers, providers)
evals/           one folder per eval; mentees copy _template/ to start
analysis/        rollup.py unifies .eval logs into a single long-form dataframe
site/            Next.js App Router dashboard — reads rollup.json, static-exported to GitHub Pages
tests/           CI: schema validation + smoke-run every eval under Haiku
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
- `OPENAI_API_KEY` — optional. When present, every eval also runs against `openai/gpt-4o`, populating the cross-provider columns on the site.
- `SLACK_WEBHOOK_URL` — optional. When present, the workflow posts a summary to the configured Slack channel after each successful run (per-eval × provider mean table, calibration AUROC, baseline scores, Δ vs. the previous rollup) and a short failure notification when the run dies. No-op when unset, so unconfigured forks don't try to post anywhere.

Deploying to GitHub Pages: the site is a fully static Next.js export, published by the [`deploy-pages`](.github/workflows/deploy-pages.yml) workflow. One-time setup: in **Settings → Pages**, set **Source** to **GitHub Actions**. The workflow runs on pushes to `main` that touch `site/**` (including the weekly `rollup.json` refresh) and on manual dispatch; the published URL is `https://<owner>.github.io/civic-evals/`.

It's served from the `/civic-evals` project subpath via `NEXT_PUBLIC_BASE_PATH` (set in the workflow). For a custom domain or a `<owner>.github.io` user repo, leave that variable unset so the site builds for the root path. Build locally with `pnpm build` (output in `site/out/`).

## Contributing a new eval

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Short version: copy `evals/_template/`, fill in `tasks.jsonl`, `eval.py`, and `README.md`, open a PR. CI validates schema and smoke-runs your eval against Haiku.

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
