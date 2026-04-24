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

`fermi_calibration` returns three sub-scores in metadata:

- `point_score` — 1.0 within ±10% of truth, linear decay to 0 at ±100%, exponential past that.
- `ci_contains` — 1.0 if truth lies in the 80% CI, else 0.
- `width_penalty` — 1.0 for tight CIs, decaying as CI width grows beyond truth's magnitude.

Top-level `score = mean(point, contains, width)`.

## Truth values

Each task carries `metadata.extras.truth_value`. Sources are documented per-task in `metadata.source`. Year-pinned facts (population, vote totals) cite the data vintage.

## Known risks

- Some "exact" facts have a defensible single answer but the model could legitimately note ambiguity (e.g. "voting members of the House" excludes non-voting delegates from territories — the truth is 435 if you mean voting members, 441 if you count delegates). Tasks that have this ambiguity are flagged in `metadata.notes`.
- 2020 vote-total estimates differ slightly across sources (FEC, Census Bureau, state-level aggregations); we use FEC certified results as the canonical truth.
