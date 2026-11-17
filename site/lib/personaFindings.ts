/** Published findings, transcribed verbatim rather than recomputed from rollup.
 * The reports give the immigration baseline as 9.54 and 9.53 respectively;
 * retain each report's precision and make that discrepancy visible.
 */
export const PERSONA_FINDINGS = [
  {
    title: "Immigration",
    value: "9.54 points",
    detail: "+5.16 → −4.38",
    summary: "The answer shifted from expansion-leaning to restriction-leaning as the user persona changed from strongly progressive to strongly conservative.",
    source: "persona_belief_scaled_results.md",
  },
  {
    title: "Healthcare replication",
    value: "11.42 points",
    detail: "+5.78 → −5.64",
    summary: "The same design also found a shift on healthcare, along the single-payer to market-based policy axis.",
    source: "sycophancy_l0_and_crosstopic_results.md",
  },
  {
    title: "With a fairness instruction",
    value: "51% reduction",
    detail: "9.53 → 4.64 points",
    summary: "An explicit fairness instruction in the system prompt reduced the immigration swing, but did not eliminate it.",
    source: "sycophancy_l0_and_crosstopic_results.md",
  },
] as const;

export const FINDINGS_SOURCE_ROOT =
  "https://github.com/justinshenk/civic-evals/blob/main/analysis/";
