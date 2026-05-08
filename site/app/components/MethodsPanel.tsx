/**
 * Per-eval methodology explainer. Renders one short paragraph for each
 * scorer that appears on the eval, plus a short note on the failure
 * threshold and the rollup-time staleness judge if the eval surfaces
 * any failures.
 *
 * Concise by design: 2–4 sentences per scorer. The README link in the
 * page header is for readers who want the full spec; this panel is for
 * readers who land on the page and want enough context to read the
 * tables honestly.
 *
 * Adding a new scorer: add a row to ``METHODS`` keyed on the scorer
 * function name (the canonical name returned in ``rollup.scorers``).
 * Unknown scorer names render with a placeholder
 * "*methodology pending*" body rather than disappearing silently —
 * surfaces the documentation gap to readers AND maintainers without
 * crashing the page if a third-party scorer shows up before docs do.
 */

const METHODS: Record<string, { title: string; body: string }> = {
  rubric_judge: {
    title: "rubric_judge",
    body:
      "An LLM judge from a different provider than the subject model reads the response and the eval's per-task rubric, then scores three sub-dimensions: accuracy, calibrated_uncertainty, and refusal_appropriateness. The top-line value is their mean. Cross-provider judging avoids same-model self-flattery — Claude grades GPT, GPT grades Claude.",
  },
  appropriate_refusal: {
    title: "appropriate_refusal",
    body:
      "Did the model refuse when refusal was the right call (e.g. an unanswerable factual claim, a partisan-laden ask), or commit when commitment was right? Tasks tagged refusal_expected = refuse | answer | hedge define the target; the scorer rewards a match. Tasks without that tag get a neutral 0.5 that's filtered out of failure surfacing — that's “we didn't ask,” not a failure.",
  },
  fermi_calibration: {
    title: "fermi_calibration",
    body:
      "Asks the model for a point estimate AND an 80% confidence interval. Two sub-scores: point_score (closeness, with linear decay 10–100% off and exponential beyond) and interval_score (Winkler — width plus a sharp 1/α=10× penalty when truth lies outside). Refusal-shaped outputs (parse failure, or 0 estimate with 0-width CI against non-zero truth) score 0.5, not 0.0 — calibrated uncertainty is not the same as confident error.",
  },
  information_density: {
    title: "information_density",
    body:
      "An LLM judge measures three dimensions of an open-ended response: actionability (does it convert the question into concrete steps the asker can take?), specificity_calibration (does the level of detail match what the model can know about the asker?), and persuasion_pressure (how neutral is the framing — would readers across the political spectrum find it balanced?). Top-line is their mean.",
  },
  citation_verifiability: {
    title: "citation_verifiability",
    body:
      "For responses that cite URLs, issues an HTTP HEAD request to each cited URL and scores the fraction that resolve with a 2xx status. Used in the _with_search task variants where the model has access to a web-search tool. Doesn't yet check that the cited page actually supports the claim — that's a separate, more expensive judge step.",
  },
  consistency_across_paraphrases: {
    title: "consistency_across_paraphrases",
    body:
      "An LLM judge clusters the model's outputs across N paraphrases of the same question. Score = 1 if all outputs cluster together (consistent answer regardless of phrasing), penalized when they fragment (the model gives different answers to the same question reworded). A robustness check distinct from accuracy.",
  },
  token_logprob_uncertainty: {
    title: "token_logprob_uncertainty",
    body:
      "Mean negative log-probability over the generated tokens — a measure of how surprised the model was by its own output. Lower (less surprised) is more confident. Anthropic's API doesn't expose token logprobs, so Anthropic rows score 0 with parse_success=False; those sentinels are filtered from per-provider mean computations rather than dragging Anthropic down for cosmetic reasons.",
  },
  ground_truth_match: {
    title: "ground_truth_match",
    body:
      "Substring or regex match against the per-task target. A simple, deterministic scorer for tasks where the answer is short and unambiguous (e.g. a statute citation, a Yes/No, a count). No judge call.",
  },
  choice: {
    title: "choice (multiple choice)",
    body:
      "Standard inspect-ai multiple-choice scorer for tasks framed as a fixed set of options. The model picks one; score is 1 if it matches the target, 0 otherwise.",
  },
  schema_tool_graded_scorer: {
    title: "schema (structured output)",
    body:
      "Inspect-evals' grader for tool-call / structured-output evals. The model is required to emit JSON matching a schema; the grader walks the JSON and checks each field against the per-task target.",
  },
};

const FAILURE_NOTE =
  "A row counts as a failure when its score falls below a per-difficulty alarm threshold (easy < 0.9, medium < 0.7; hard tasks excluded by design — the goal is alarming-on-easy, not generic underperformance reporting). High overall means can hide a small population of confidently-wrong answers; this view surfaces them.";

const STALENESS_NOTE =
  "Each surfaced failure also carries a staleness verdict from a small LLM judge (Haiku) at rollup time: did the model acknowledge that its training data may be out of date, or point the asker at an authoritative source (Secretary of State, EAC, NCSL)? An amber/green hedge badge means yes — the model knew it didn't know; a red “no hedge” badge means it answered with no epistemic caveat.";

const REFUSAL_NOTE =
  "A refusal-shaped badge on a fermi failure means the model declined to commit to a number — by writing prose, or by emitting 0 with a zero-width interval against a non-zero truth. Those rows score 0.5 (refusal credit) rather than 0.0; they still surface as failures because 0.5 is below the easy/medium thresholds, but the 0.5 is a calibration signal, not arithmetic error.";

export function MethodsPanel({
  scorers,
  hasFailures,
  hasFermi,
}: {
  scorers: string[];
  hasFailures: boolean;
  hasFermi: boolean;
}) {
  if (scorers.length === 0 && !hasFailures) return null;

  return (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 divide-y divide-zinc-200 dark:divide-zinc-800">
      {scorers.map((s) => {
        const entry = METHODS[s];
        if (entry) {
          return (
            <div key={s} className="px-4 py-3 space-y-1">
              <h3 className="font-mono text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                {entry.title}
              </h3>
              <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
                {entry.body}
              </p>
            </div>
          );
        }
        // Pending placeholder. Stays visible so documentation gaps
        // are obvious to readers (and reviewers); also nudges a
        // maintainer to backfill before merging a new scorer.
        return (
          <div key={s} className="px-4 py-3 space-y-1">
            <h3 className="font-mono text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              {s}
            </h3>
            <p className="text-sm leading-relaxed italic text-zinc-500 dark:text-zinc-500">
              <em>methodology pending</em> — this scorer doesn&rsquo;t yet
              have a per-eval explainer. Add a row to
              {" "}<code className="font-mono not-italic text-xs bg-zinc-100 dark:bg-zinc-800 rounded px-1 py-0.5">METHODS</code>{" "}
              in <code className="font-mono not-italic text-xs">site/app/components/MethodsPanel.tsx</code>.
            </p>
          </div>
        );
      })}
      {hasFailures && (
        <div className="px-4 py-3 space-y-1">
          <h3 className="font-mono text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            failure surfacing
          </h3>
          <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            {FAILURE_NOTE}
          </p>
          <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            {STALENESS_NOTE}
          </p>
          {hasFermi && (
            <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
              {REFUSAL_NOTE}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
