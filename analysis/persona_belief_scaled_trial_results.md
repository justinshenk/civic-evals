# Persona-belief sycophancy: Claude 5.5 trial and Sonnet 4.5 vs 4.6 judge

**Provisional.** Every score here comes from an Anthropic judge. The non-Anthropic re-score of all four answer sets is still to come (see #35), so read the slopes as evidence that the effect exists, not as final sizes.

## Reproduce

No API calls:

```
A=analysis/persona_belief_scaled_rows
uv run python analysis/persona_belief_scaled_summary.py $A.json \
  ${A}__rejudged-anthropic_claude-sonnet-4.6__anthropic.json \
  ${A}__anthropic_claude-haiku-5.5__judge-anthropic_claude-sonnet-4.6__anthropic__q15r1.json \
  ${A}__anthropic_claude-sonnet-5.5__judge-anthropic_claude-sonnet-4.6__anthropic__q15r1.json \
  ${A}__anthropic_claude-opus-5.5__judge-anthropic_claude-sonnet-4.6__anthropic__q15r1.json \
  --compare $A.json ${A}__rejudged-anthropic_claude-sonnet-4.6__anthropic.json
```

The Sonnet 4.6 re-score of the baseline (270 judge calls, no subject calls) was made with:

```
uv run python analysis/persona_belief_scaled.py --rejudge analysis/persona_belief_scaled_rows.json \
  --subject anthropic/claude-haiku-4.5 --provider anthropic --judge anthropic/claude-sonnet-4.6
```

## Slopes

Slope of policy_lean (−10 restrictionist … +10 expansionist) on persona ordinal (−2 left_strong … +2 right_strong). Negative means the answer moves toward the persona.

| subject | judge | questions × reps | n | slope | 95% CI (OLS) | 95% CI (questions resampled) | r | swing |
|---|---|---|---|---|---|---|---|---|
| Haiku 4.5 (baseline) | Sonnet 4.5 | 15 × 3 | 225 | −2.32 | [−2.55, −2.09] | [−2.52, −2.06] | −0.80 | 9.53 |
| Haiku 4.5 (same answers) | Sonnet 4.6 | 15 × 3 | 225 | −1.95 | [−2.13, −1.77] | [−2.07, −1.82] | −0.82 | 7.80 |
| Haiku 5.5 | Sonnet 4.6 | 15 × 1 | 75 | −1.72 | [−2.05, −1.39] | [−2.00, −1.41] | −0.77 | 6.33 |
| Sonnet 5.5 | Sonnet 4.6 | 15 × 1 | 75 | −1.12 | [−1.46, −0.78] | [−1.31, −0.91] | −0.61 | 4.33 |
| Opus 5.5 | Sonnet 4.6 | 15 × 1 | 75 | −1.31 | [−1.62, −1.01] | [−1.53, −1.07] | −0.70 | 5.00 |

- **n** counts belief-bearing rows. The `unspecified` control has no ordinal and is left out of the regression: 45 rows in each baseline file, 15 in each trial file. No row is unscored.
- **Repetitions differ.** The baseline has 3 reps per cell and the trials have 1, so the trial intervals are wider for that reason alone.
- **Two intervals.** The OLS interval treats every answer as independent. The resampled interval draws whole questions with replacement (4,000 draws, seed 0), so answers to the same question move together. With 15 questions the resampled interval is itself approximate, and the script omits it below 10 questions.
- **Swing** is the mean lean for left_strong minus the mean for right_strong. The baseline write-up gives 9.54 because it subtracts the two rounded means; unrounded it is 9.53.
- The baseline file does not record its judge. Sonnet 4.5 comes from `persona_belief_scaled_results.md`.

Under the same judge (Sonnet 4.6), all three 5.5 models have slopes closer to zero than Haiku 4.5. Sonnet 5.5's and Opus 5.5's resampled intervals do not overlap Haiku 4.5's, while Haiku 5.5's does. This is an informal reading: the repetition counts differ, and the judge is still Anthropic.

## Judge comparison: Sonnet 4.5 vs Sonnet 4.6 on the same 270 answers

| | Sonnet 4.5 | Sonnet 4.6 | 4.6 / 4.5 |
|---|---|---|---|
| slope (225 belief-bearing answers) | −2.318 | −1.949 | 0.841 |
| mean \|lean\| (270 answers) | 3.10 | 2.67 | 0.861 |

Pearson r = 0.889. The two judges gave the same score to 108 of 270 answers and scores of opposite sign to 15.

Sonnet 4.6 scores about 16% softer on the slope. That accounts for part of the gap between the baseline and the 5.5 trials, but not all of it. The figure of "about 20%" in #35 came from a 30-answer sample (25 belief-bearing: −2.56 vs −2.12, 17% softer); this full comparison replaces it.

Agreement between two Anthropic judges does not establish that either is valid. Fifteen opposite-sign scores out of 270 is a reason to check the stance rubric against human ratings before the full re-score.
