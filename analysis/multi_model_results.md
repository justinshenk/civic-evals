# Cross-model substantive-policy bias on candidate ratings

A factorial-design measurement of whether language models rate hypothetical political candidates differently based on the substantive direction of their stated policy positions, after controlling for stated qualifications. Six models compared via OpenRouter.

## What was measured

For a single scenario (open seat on a US school board, 50,000-student district), the script renders synthetic candidate profiles across a 24-cell factorial:

- **party_label** ∈ {Democrat, Republican} — *should not matter*
- **policy_package** ∈ {D-typical, R-typical} — *should not matter*
- **experience** ∈ {junior, mid, senior — 2 / 8 / 16 yr} — *should matter*
- **rigor** ∈ {thin platform, deep platform with named bills + dollar figures} — *should matter*

Each profile is sent to the model with a request to rate the candidate 1–10. OLS decomposes the rating variance:

```
rating ~ party_label + policy_package + experience + rigor + (party_label x policy_package)
```

with z-standardized predictors. The `policy_package` coefficient measures whether the model rates D-typical vs R-typical platforms differently when label, experience, and rigor are held constant.

The two policy packages cover the same four areas (infrastructure, public safety, education, spending), match on rigor markers (named legislation, dollar figures, acknowledged tradeoffs), and use **identical dollar magnitudes**. Only the substantive direction differs — for example:

- **D-typical infrastructure:** SB 412, $2.1B bond for transit + clean-energy retrofits, funded via 0.5% corporate tax adjustment
- **R-typical infrastructure:** SB 412, $2.1B bond for road + bridge repair, funded via reallocating $140M/yr in non-essential spending

Same fiscal seriousness; different ideological direction. A model that rates the two differently is reacting to the substance, not to the rigor.

## Headline metric: years-of-experience equivalent

Standardized regression coefficients are technically right but uninterpretable. The script also fits an unstandardized OLS with experience encoded in *years* and reports the ratio:

```
yrs/pkg = -β_policy_package_raw / β_experience_per_year_raw
```

which reads as: *"holding everything else equal, advocating Republican-typical positions costs the candidate this many years of equivalent experience in the model's eyes."*

For context: experience tiers in the prompt template are 2 / 8 / 16 years, so an effect of "8 years" is roughly the gap between *junior* and *senior*.

## Run setup

- **Date:** 2026-05-07
- **Driver:** `analysis/multi_model_bias.py`
- **Templates:** `analysis/bias_templates.py`
- **Raw rows:** `analysis/multi_model_rows.json`
- **Cells:** 24 per model
- **Replicates:** 5 per cell → 120 obs per model
- **Total subject calls:** 720 (115–120 parsed per model; 4 parse failures total, all on Llama)

## Results

| model | β_package (z-z) | p | yrs/package | yrs/party | rating sd | R² |
|---|---|---|---|---|---|---|
| `meta-llama/llama-3.3-70b-instruct` | **−0.391** | 1.95×10⁻¹⁷ | **+9.11** | +0.47 | 1.71 | 0.836 |
| `anthropic/claude-haiku-4.5` | −0.382 | 7.70×10⁻¹⁴ | **+8.66** | −3.71 | 0.83 | 0.770 |
| `openai/gpt-4o-mini` | −0.346 | 6.74×10⁻¹⁷ | **+7.24** | +1.76 | 1.47 | 0.859 |
| `google/gemini-2.5-flash` | −0.306 | 7.49×10⁻¹¹ | **+5.56** | −0.26 | 1.37 | 0.795 |
| `qwen/qwen-2.5-72b-instruct` | −0.213 | 2.79×10⁻³ | **+4.01** | −0.00 | 1.41 | 0.445 |
| `deepseek/deepseek-chat` | −0.228 | 9.48×10⁻⁹ | **+2.87** | +0.17 | 1.54 | 0.846 |

`p_party` (party-label coefficient on its own) is not significant for any model — all p ≥ 0.08. The bias is on substantive policy content, not on the word "Democrat" vs "Republican."

## What this run shows

### 1. The bias generalizes across providers

Every model shows a statistically significant `policy_package` coefficient, all in the same direction (D-typical platforms rated higher than R-typical, controlling for label, experience, and rigor). Across Anthropic, OpenAI, Google, an open-source Llama, and two non-Western Chinese-lab models, no model in the sample is on the other side of zero.

### 2. The bias is on substance, not labels

Across all six models the standardized coefficient on `party` alone is small and not significant (best p = 0.08 for gpt-4o-mini). The hypothesis that "models are biased against Republicans by label" is not supported here; the hypothesis that "models are biased against Republican-typical *policies*" is supported across the board.

### 3. The "less safety-tuning = more bias" prior didn't hold

Going in, the expectation was that open-source / non-Western models would show larger bias because they have less RLHF for political balance. The data ordered the opposite way:

```
LARGEST bias                                                  SMALLEST
Llama-70b (open-source)  >  Haiku (safety-tuned)  > ... > DeepSeek (Chinese lab)
+9.1 yr                     +8.7 yr                          +2.9 yr
```

DeepSeek and Qwen — the two Chinese-lab models — sit at the bottom of the magnitude ranking. Llama (open-source) and Haiku (heavily safety-tuned) sit at the top.

Possible mechanisms — none of which we can distinguish from this run alone:

- **Cultural distance.** DeepSeek and Qwen may be less calibrated to which US-coded policy positions are R-typical vs D-typical. If the model doesn't strongly recognize "outcome-based school funding + school choice" as Republican-coded, it can't penalize R-coded content as strongly.
- **Rating consistency.** Qwen's R² is 0.445 — about half the other models'. A lot of its rating variance is unexplained by the experimental factors, meaning it's giving more random/noisy ratings, which dampens any structural bias coefficient. This is a measurement artifact more than a finding.
- **DeepSeek is the more interesting case.** R² = 0.846 (high — comparable to gpt-4o-mini and Llama), yet β_package = −0.228 (smallest). DeepSeek's ratings are *consistent* but show less policy-substance preference. Worth investigating.

### 4. Years-equivalent translation makes the magnitude land

Saying "β_package = −0.382, p = 10⁻¹⁴" is technically correct but doesn't communicate scale. Saying "Haiku rates a candidate advocating Republican-typical positions as roughly 8.7 years less experienced" is concrete. Eight-and-a-half years is roughly the gap between a junior city-council member and a sixteen-year veteran legislator — material in candidate-evaluation terms, not a rounding error.

## Caveats

- **One scenario only** (school_board). Earlier per-scenario data (not in this analysis) suggested this is where the substantive-policy effect was largest among five candidate scenarios; mayoral was second; state legislature, US House, and gubernatorial scenarios showed minimal `policy_package` effects in single-rep runs. The cross-model story may look very different on those scenarios; this run does *not* claim to cover them.
- **N=120 per model.** Plenty for the headline coefficient (SE ~0.04 on β_package, smallest detected effect at t ≈ 3) but not enough to nail down the small `party`-only effects.
- **OpenRouter routing.** OpenRouter may proxy through a different inference stack than the direct Anthropic SDK; the OpenRouter Haiku β_package (−0.382) is close to but not identical to a direct-SDK 10-rep run on the same templates (−0.313). Likely a sampling-temperature / routing difference (we did not pin temperature for the OpenRouter calls).
- **No instruction-tuning correction.** The same prompt template was used across all six models. Models with different default behaviors (e.g. Qwen's lower R²) may be reacting partly to prompt-format mismatch rather than to the substantive content.
- **The bias direction is left-leaning on the policy axis we tested.** The templates use a particular pair of "D-typical" and "R-typical" platforms; results may shift if the templates emphasize different policy areas. The four areas (infrastructure, public safety, education, spending) and matched dollar magnitudes were held constant, but the choice of *which* areas to include is itself a design decision.

## How to reproduce

```
set -a; source .env; set +a
python analysis/multi_model_bias.py
```

The script writes raw per-call data to `analysis/multi_model_rows.json` so the regression can be re-run without re-hitting the API. Templates live in `analysis/bias_templates.py` and are stable across this and other analyses in the same folder.

Required environment: `OPENROUTER_API_KEY` set in `.env` or shell.
