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
tests/           CI: schema validation + smoke-run every eval under Haiku
logs/            .eval outputs (gitignored)
```

## Contributing a new eval

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Short version: copy `evals/_template/`, fill in `tasks.jsonl`, `eval.py`, and `README.md`, open a PR. CI validates schema and smoke-runs your eval against Haiku.

## Research agenda

This scaffolding is the foundation for experiments on:

- **Persona-conditioned bias** — varying attributes that shouldn't matter (political lean, profession, language fluency) and measuring whether the model's accuracy, tone, or refusal pattern shifts.
- **Confidence calibration** — does the model's stated confidence track its actual accuracy? Fermi-style estimation under civic framings.
- **Appropriate refusal** — both failure modes matter: confidently inventing voter-ID policy, or refusing to explain a real one.
- **Citation verifiability** — when the model cites, does the source exist and support the claim.

The three reference evals (`voting_access`, `election_integrity`, `policy_impact_personalization`) demonstrate how to wire each of these into the shared infrastructure.
