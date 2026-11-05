# Figure 6 audited comparison — base Qwen3-14B vs PCT

Inference uses 12 matched `(party, experience, rigor)` prompt strata; five generations are averaged within each prompt before testing.

| arm | parsed | D-typical − R-typical gap | 95% CI | prompt-level p | β package | years/package |
|---|---:|---:|---:|---:|---:|---:|
| Base | 120/120 | 0.633 | [0.374, 0.892] | 0.0002221 | -0.225 | 3.36 |
| PCT | 120/120 | 0.100 | [-0.133, 0.333] | 0.3652 | -0.041 | 0.21 |

## Treatment contrast

PCT changed the package gap by **-0.533 points** (95% CI [-0.851, -0.216]; paired t p=0.003518; exact sign-flip p=0.007812).
This is an **84.2% reduction** in the mean gap.

## Interpretation boundary

This supports transfer from PCT to this candidate-rating task. It does not establish that all candidate-judgment bias is fixed: the experiment uses one school-board scenario selected after earlier work found a large package effect, only 12 matched prompt strata, and synthetic profiles with some office-history inconsistencies.
