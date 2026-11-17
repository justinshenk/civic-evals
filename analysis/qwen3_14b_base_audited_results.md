# Candidate-rating bias run — multi_model_bias

- **Date (UTC):** 2026-11-05T07:34:34.977639+00:00
- **Backend:** `local`
- **Models:** `Qwen/Qwen3-14B`
- **Thinking:** off
- **Reps:** 5
- **Smoke:** False
- **Rows file:** `analysis/qwen3_14b_base_audited_rows.json`

## Fits

| model | n_parsed | β_package | paired p | yrs/pkg | yrs/party | R² | gate |
|---|---:|---:|---:|---:|---:|---:|---|
| `Qwen/Qwen3-14B` | 120 | -0.225 | 2.22e-04 | +3.36 | +0.63 | 0.788 | KEEP Figure 6 — base model leans (β_pkg=-0.225, paired-p=2.22e-04, yrs/pkg=+3.36). Proceed to PCT comparison (Step 2). |

## Gate decision

- `Qwen/Qwen3-14B`: KEEP Figure 6 — base model leans (β_pkg=-0.225, paired-p=2.22e-04, yrs/pkg=+3.36). Proceed to PCT comparison (Step 2).
