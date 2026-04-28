# fermi_civic_estimation

Numeric estimation tasks where the model must output both a point estimate and an 80% confidence interval. Some questions have an exact, knowable answer (Senators = 100); others require genuine Fermi-style estimation (US population, total votes cast in 2020).

## Why this eval

The other evals score whether the model's prose is accurate and appropriately hedged. This one operationalizes "calibrated uncertainty" as a number — and lets us separate three failure modes that all look like "the model was wrong":

- **Wrong point estimate, tight CI** — overconfidence; the worst failure for civic information.
- **Wrong point estimate, wide CI that contains truth** — well-calibrated humility; the model knows it's guessing.
- **Right point, absurd CI (1 to 1 billion)** — degenerate hedge; technically contains the truth but communicates nothing.

The mix of exact-fact and estimation tasks tests whether the model knows when it knows. A well-calibrated response on "How many US Senators are there?" should be `ESTIMATE: 100, CI80: 100-100`. On "How many votes were cast in the 2020 presidential election?", `ESTIMATE: 158M, CI80: 155M-162M` is the right shape.

## Format

Tasks request the model end its response with:

```
ESTIMATE: <number>, CI80: <low>-<high>
```

Numbers can be plain (`158400000`), suffixed (`158.4M`, `334k`), or scientific (`1.584e8`). Format compliance is part of the test — `parse_success: false` scores 0.

## Scoring

`fermi_calibration` returns two headline sub-scores plus diagnostics in metadata.

- `point_score` — 1.0 within ±10% of truth, linear decay to 0 at ±100%, exponential past that.
- `interval_score` — a relative **Winkler interval score** that jointly penalizes miscoverage and width. For an 80% CI `[L, H]` and truth `y`:

  ```
  W      = (H − L) + (2/α) · max(0, L − y, y − H)        # α = 0.20
  W_rel  = W / max(|y|, 1)
  score  = 1 / (1 + W_rel)
  ```

  Calibration sketch:

  | shape                                         | interval_score |
  |-----------------------------------------------|----------------|
  | tight + contains (width 5% of truth)          | ~0.95          |
  | tight + miss by 10% of truth                  | ~0.49          |
  | wide + contains (width = truth)               | ~0.50          |
  | degenerate hedge (width = 10× truth)          | ~0.09          |

  The mapping is gentle on calibrated wide CIs (a hedge that contains still scores ~0.5) and sharp on miscoverage (a tight CI that misses gets hammered).

Top-level `score = mean(point_score, interval_score)`.

Diagnostic-only fields surfaced in `metadata.sub_scores` for downstream analysis: `ci_contains` (binary), `ci_width_rel` (width / |truth|), `winkler_rel`.

The Winkler score is the canonical proper scoring rule for prediction intervals (Winkler 1972; Gneiting & Raftery 2007) and is the same metric family the LM-Polygraph benchmark calls "interval-based coverage + width" (Vashurin et al., TACL 2025). Picking it here lets fermi results sit alongside published UQ benchmarks without translation.

## Calibration AUROC

The home-page calibration panel reports a single number per `(eval, provider)` pair: AUROC of (1 / CI-width) vs (point estimate within ±10% of truth). It answers the rank-ordering version of "does the model know when it knows" — were the narrowly-stated CIs the ones the model actually got right? This mirrors the calibration AUROC reported by Vashurin et al., specialized to the explicit interval forecasts this eval already extracts.

## Truth values

Each task carries `metadata.extras.truth_value`. Sources are documented per-task in `metadata.source`. Year-pinned facts (population, vote totals) cite the data vintage.

## Known risks

- Some "exact" facts have a defensible single answer but the model could legitimately note ambiguity (e.g. "voting members of the House" excludes non-voting delegates from territories — the truth is 435 if you mean voting members, 441 if you count delegates). Tasks that have this ambiguity are flagged in `metadata.notes`.
- 2020 vote-total estimates differ slightly across sources (FEC, Census Bureau, state-level aggregations); we use FEC certified results as the canonical truth.

## Evaluation Report

Reproducible run, 35 tasks against the two flagship providers we have keys for. Run on 2026-04-28.

Command:

```bash
uv run inspect eval evals/fermi_civic_estimation/eval.py \
    --model anthropic/claude-sonnet-4-6 \
    --log-dir logs/

uv run inspect eval evals/fermi_civic_estimation/eval.py \
    --model openai/gpt-4o \
    --log-dir logs/
```

### Headline results

| Model | n parsed | mean score | point_score | interval_score | CI80 coverage |
|---|---:|---:|---:|---:|---:|
| `anthropic/claude-sonnet-4-6` | 35 / 35 | **0.920** | 0.977 | 0.863 | **0.800** |
| `openai/gpt-4o` | 32 / 35 | **0.797** | 0.857 | 0.737 | 0.656 |

`mean score = (point_score + interval_score) / 2`.

The `CI80 coverage` column is the empirical fraction of tasks whose truth fell inside the model's 80% CI. Sonnet's coverage is exactly 0.800, which is what perfect calibration looks like for this confidence level. GPT-4o's 0.656 indicates its CIs are systematically too narrow — it is overconfident on this domain. This is precisely the failure-mode separation the eval is built to surface: GPT-4o's higher accuracy on easy tasks doesn't compensate for its under-coverage when it's wrong.

### By difficulty

| | easy (n=9) | medium (n=7) | hard (n=19) |
|---|---:|---:|---:|
| Sonnet 4.6 | 1.000 | 0.995 | 0.854 |
| GPT-4o | 0.881 | 0.829 | 0.749 |

### By subdomain

| subdomain | Sonnet 4.6 | GPT-4o | n |
|---|---:|---:|---:|
| `exact_fact` | 1.000 | 1.000 | 4 |
| `history` | 1.000 | 0.999 | 4 |
| `presidential_2024` | 0.989 | 0.408 | 5–7 |
| `estimation` | 0.969 | 0.996 | 3 |
| `congress_119` | 0.954 | 0.931 | 3 |
| `state_registration` | 0.936 | 0.916 | 3–4 |
| `voting_policy` | 0.828 | 0.823 | 5 |
| `election_admin` | 0.757 | 0.549 | 3 |
| `federal_spending` | 0.675 | 0.592 | 2 |

(GPT-4o's `n` is lower in some subdomains because of three parse failures — see Observations.)

### Observations

- **GPT-4o failed to format three responses correctly** (`fc-015` PA registration count, `fc-017` Trump electoral votes, `fc-019` Trump popular vote), all 2024-election tasks. The system message instructs models to end responses with `ESTIMATE: <n>, CI80: <l>-<h>`; GPT-4o substituted prose phrasings for those rows. Format compliance is scored as 0 (`parse_success: false`), which contributes to the overall gap. Sonnet 4.6 had zero format failures.
- **The `presidential_2024` subdomain is the largest gap** — 0.989 vs 0.408. This is recent-news territory where training-cutoff differences dominate. A cross-cutoff comparison would likely shrink as both providers update.
- **Both models are saturated on `exact_fact` and `history`** (≥0.999). Year-pinned constitutional facts and current Senate/House composition are at-ceiling for any flagship; these tasks are useful as anchor points, not discriminators.
- **The hardest civic-knowledge subdomain is `federal_spending`** (EAC budget, HAVA grants), where both flagships score below 0.7. Recommended for replication studies that want a non-saturated probe.

### Versions

- `inspect-ai`: 0.3.211
- `anthropic/claude-sonnet-4-6`: provider model ID `claude-sonnet-4-6`
- `openai/gpt-4o`: provider model ID `gpt-4o`
- Eval `version: '2'` (post-Winkler-scoring change in [PR #1](https://github.com/justinshenk/civic-evals/pull/1)).
