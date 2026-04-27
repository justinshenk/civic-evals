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
