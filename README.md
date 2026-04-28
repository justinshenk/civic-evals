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

## Repo layout

```
src/p3/          shared infrastructure (schema, personas, scorers, providers)
evals/           one folder per eval; mentees copy _template/ to start
analysis/        rollup.py unifies .eval logs into a single long-form dataframe
site/            Next.js App Router dashboard — reads rollup.json, deploys to Vercel
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

The `refresh-results` GitHub Action runs the eval suite on a weekly schedule (and on `workflow_dispatch`), regenerates `rollup.json`, and commits the update. Vercel picks up the commit and redeploys automatically.

Repo secrets (set under `Settings → Secrets and variables → Actions`):

- `ANTHROPIC_API_KEY` — required.
- `OPENAI_API_KEY` — optional. When present, every eval also runs against `openai/gpt-4o`, populating the cross-provider columns on the site.
- `SLACK_WEBHOOK_URL` — optional. When present, the workflow posts a summary to the configured Slack channel after each successful run (per-eval × provider mean table, calibration AUROC, baseline scores, Δ vs. the previous rollup) and a short failure notification when the run dies. No-op when unset, so unconfigured forks don't try to post anywhere.

Deploying to Vercel: `vercel login && vercel` from the `site/` directory, or import the repo through the Vercel dashboard with **Root Directory** set to `site`.

## Contributing a new eval

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Short version: copy `evals/_template/`, fill in `tasks.jsonl`, `eval.py`, and `README.md`, open a PR. CI validates schema and smoke-runs your eval against Haiku.

## Research agenda

This scaffolding is the foundation for experiments on:

- **Persona-conditioned bias** — varying attributes that shouldn't matter (political lean, profession, language fluency) and measuring whether the model's accuracy, tone, or refusal pattern shifts.
- **Confidence calibration** — does the model's stated confidence track its actual accuracy? Fermi-style estimation under civic framings.
- **Appropriate refusal** — both failure modes matter: confidently inventing voter-ID policy, or refusing to explain a real one.
- **Citation verifiability** — when the model cites, does the source exist and support the claim.

The three reference evals (`voting_access`, `election_integrity`, `policy_impact_personalization`) demonstrate how to wire each of these into the shared infrastructure.

## Methodology notes

The scoring layer is intentionally aligned with the LM-Polygraph benchmark (Vashurin et al., [TACL 2025](https://aclanthology.org/2025.tacl-1.11/)) so results sit alongside published UQ work without translation:

- `fermi_calibration.interval_score` is a relative Winkler interval score — the canonical proper scoring rule for prediction intervals (Winkler 1972; Gneiting & Raftery 2007), which LM-Polygraph aggregates as "interval-based coverage + width."
- `rubric_judge.calibrated_uncertainty` is a verbalized / claim-level UQ signal: one confidence assessment per generated claim, judged by a different-provider LLM.
- `token_logprob_uncertainty` is the cheapest LM-Polygraph baseline — mean negative token logprob. Currently OpenAI-only since Anthropic doesn't expose token logprobs in its API.
- `analysis/rollup.py` reports a per-(eval, provider) **calibration AUROC**, mirroring the LM-Polygraph headline metric specialized to interval forecasts.

`CONTRIBUTING.md` has a more detailed mapping for mentees designing new calibration-style evals.
