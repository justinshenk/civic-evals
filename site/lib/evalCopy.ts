/**
 * Plain-language title + summary per eval, for a non-technical reader.
 *
 * Faithful condensations of each eval's own `description` (see
 * rollup.json `evals_meta`) — they simplify wording, they don't add
 * claims. Cards and the per-test detail page show this version; the
 * original technical description stays available next to it. Evals
 * without an entry fall back to their raw name + description, so a
 * newly-added eval still renders (just less friendly) until someone
 * writes its plain summary here.
 */
export const EVAL_COPY: Record<string, { title: string; summary: string }> = {
  voting_access: {
    title: "Voting access",
    summary:
      "Everyday facts about voting in the U.S.: how to register, what ID you need, where and when to vote, and how to get on the ballot.",
  },
  election_integrity: {
    title: "Election integrity",
    summary:
      "Whether a model handles claims about U.S. elections correctly — debunking known falsehoods, confirming true procedures without needless hedging, and pointing people to official state sources when the answer depends on where they live.",
  },
  fermi_civic_estimation: {
    title: "Estimating numbers",
    summary:
      "Asks the model for a number and how sure it is. Some answers are exact (there are 100 U.S. Senators); others need a ballpark (the U.S. population, total votes cast in 2020). Tests whether its confidence matches how well it actually knows.",
  },
  policy_impact_personalization: {
    title: "“How does this affect me?”",
    summary:
      "Asks how a policy would affect the person asking — posed as different kinds of people, where the right answer genuinely depends on who is asking.",
  },
  openendedness_ladder: {
    title: "Clear vs. open-ended questions",
    summary:
      "Questions that range from a single clear answer to wide-open and interpretive, checking how much the model's answers start to vary as the questions get fuzzier.",
  },
  persona_drift_pilot: {
    title: "Holding a position under pressure",
    summary:
      "Whether a model's stance on election-policy questions shifts based on who's asking, whether the user pushes back, or whether a false claim was planted earlier in the conversation.",
  },
};

export function evalTitle(name: string): string {
  return EVAL_COPY[name]?.title ?? name;
}
