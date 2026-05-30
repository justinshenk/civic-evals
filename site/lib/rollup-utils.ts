// Client-safe types and helpers — no node:fs imports

export type SubScores = {
  accuracy?: number;
  calibrated_uncertainty?: number;
  refusal_appropriateness?: number;
};

export type PersonaAttrs = {
  role: string;
  lang_fluency: string;
  education: string;
  political_lean: string;
  urgency: string;
  digital_literacy: string;
};

export type ScoreDiagnostics = {
  truth?: number;
  estimate?: number;
  ci_low?: number;
  ci_high?: number;
  parse_success?: boolean;
};

export type RollupRow = {
  eval: string;
  task_id: string;
  provider: string;
  persona: string;
  persona_attrs: PersonaAttrs | null;
  domain: string | null;
  subdomain: string | null;
  difficulty: string | null;
  tags: string;
  scorer: string;
  score: number | null;
  explanation: string;
  completion: string;
  sub_scores: SubScores | null;
  score_metadata: ScoreDiagnostics | null;
};

// Research-direction split per the May 2026 team pivot. "factual" =
// the task has a verifiable right answer (statute, rule, numeric truth);
// accuracy/recall is the metric. "interpretive" = no single correct
// answer (persona-conditioned advice, candidate qualifications,
// policy trade-offs); persona-conditioned drift, framing bias, and
// response variance are the metrics that matter. null on tasks that
// pre-date the field; "mixed" only at the eval level when an eval
// contains both.
export type Track = "factual" | "interpretive";
export type EvalTrack = Track | "mixed" | null;

export type TaskSummary = {
  id: string;
  input: string;
  subdomain: string;
  difficulty: "easy" | "medium" | "hard";
  tags: string[];
  persona: string | null;
  scorer_kind: "rubric" | "target";
  target: string | null;
  rubric_snippet: string | null;
  refusal_expected: "refuse" | "answer" | "hedge" | null;
  source: string;
  // ISO date (YYYY-MM-DD) when ground truth was last checked. null when
  // unverified — older than 12 months should be treated as needing
  // re-verification before the eval's mean is fully trusted.
  last_verified: string | null;
  track: Track | null;
};

export type EvalMeta = {
  name: string;
  description: string;
  task_count: number;
  difficulty: Record<string, number>;
  subdomains: string[];
  personas_used: string[];
  scorer_kinds: string[];
  // Dominant track across the eval's tasks; "mixed" when both are
  // represented. null on rollups regenerated before the field was added.
  track: EvalTrack;
  readme_url: string;
  tasks: TaskSummary[];
};

export type CalibrationStat = {
  eval: string;
  provider: string;
  metric: "calibration_auroc";
  value: number | null;
  n: number;
  n_correct: number;
  explanation: string;
};

export type FailureRow = {
  eval: string;
  task_id: string;
  difficulty: "easy" | "medium" | "hard" | string;
  persona: string;
  provider: string;
  scorer: string;
  score: number;
  threshold: number;
  explanation: string;
  completion: string;
  sub_scores: SubScores | null;
  // True when the scorer marked this row as a refusal-shaped output —
  // model declined to commit to a number rather than emitting a wrong
  // one. Currently only set by fermi_calibration. Distinct from the
  // rollup-time staleness verdict below: refused=True means the score
  // itself is a refusal credit (0.5 by convention), while
  // acknowledged_staleness is a post-hoc judgment about *why*.
  refused: boolean | null;
  // null = not judged (web-search-enabled eval, missing API key, judge crash).
  acknowledged_staleness: boolean | null;
  // "cutoff" | "source" | "variation" | "none" — null when not judged.
  staleness_kind: string | null;
  // Short quote/paraphrase the judge used to justify the verdict.
  staleness_evidence: string | null;
};

export type FailureSummaryRow = {
  eval: string;
  n_failures: number;
  n_acknowledged: number;
  n_unacknowledged: number;
  ack_rate: number | null;
};

export type FailureSummary = {
  by_eval: FailureSummaryRow[];
};

export type ExternalBaseline = {
  name: string;
  short_name: string;
  title: string;
  description: string;
  arxiv: string | null;
  source: string;
  providers: string[];
  n_rows: number;
};

// Per-(eval, scorer, provider) mean + 95% bootstrap CI.
//
// Computed in analysis/rollup.collect_cell_stats. With N=5–15 per cell
// after persona expansion, the headline mean alone invites readers to
// over-interpret 0.05 deltas. Pairing it with a bootstrap interval
// makes the spread visible. Cells with N<3 carry ci_low/ci_high=null
// — at that sample size the bootstrap is meaningless and the UI
// should show "n=2" rather than a fake-precise interval.
export type CellStat = {
  eval: string;
  scorer: string;
  provider: string;
  n: number;
  mean: number;
  ci_low: number | null;
  ci_high: number | null;
};

// Cross-model substantive-policy bias from the school-board candidate
// factorial (Eric's experiment, May 2026; analysis/multi_model_bias.py).
// One record per model; the headline metric is years_per_package — read
// as "the R-typical-platform candidate is rated as having this many
// fewer years of equivalent experience than the otherwise-identical
// D-typical candidate." Positive ⇒ D-typical rated higher.
export type BiasFit = {
  model: string;
  years_per_package: number | null;
  years_per_party: number | null;
  beta_package_zz: number | null;
  p_package: number | null;
  r2: number | null;
  rating_mean: number;
  rating_sd: number;
  n_parsed: number;
  n_total: number;
};

// Token-usage and cost per (eval, model). cost_source distinguishes
// "reported" (provider sent it) from "computed" (priced via the local
// table) so the UI can footnote estimates.
export type UsageRow = {
  eval: string;
  model: string;
  n_runs: number;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  cost_usd: number | null;
  cost_source: "reported" | "computed" | "mixed" | "unknown";
};

export type Rollup = {
  generated_at: string;
  n_rows: number;
  evals: string[];
  providers: string[];
  scorers: string[];
  evals_meta: EvalMeta[];
  calibration_stats: CalibrationStat[];
  external_baselines: ExternalBaseline[];
  failures: FailureRow[];
  failure_thresholds: Record<string, number>;
  failure_summary: FailureSummary;
  // Optional so older rollups (pre-usage feature) still parse.
  usage?: UsageRow[];
  // Optional so rollups that ran without analysis/multi_model_rows.json
  // (CI forks, smoke tests) still parse.
  bias?: BiasFit[];
  // Optional so older rollups (pre-cell-stats feature) still parse.
  cell_stats?: CellStat[];
  rows: RollupRow[];
};

/**
 * Indexed cell-stats lookup. Pre-build once per render; calling the
 * returned closure is O(1).
 *
 *   const stat = cellStatLookup(rollup.cell_stats);
 *   const s = stat(eval, scorer, provider);  // CellStat | undefined
 */
export function cellStatLookup(
  stats: CellStat[] | undefined,
): (e: string, s: string, p: string) => CellStat | undefined {
  if (!stats || stats.length === 0) return () => undefined;
  const map = new Map<string, CellStat>();
  for (const s of stats) {
    map.set(`${s.eval} ${s.scorer} ${s.provider}`, s);
  }
  return (e, s, p) => map.get(`${e} ${s} ${p}`);
}

/**
 * Render a 95% CI as a paren tail on a mean: ``0.62 [0.49–0.74] (n=12)``.
 * Falls back to just ``mean (n=N)`` when CI is null (n<3).
 */
export function fmtMeanCI(stat: CellStat | undefined, digits = 2): string {
  if (!stat) return "—";
  const mean = stat.mean.toFixed(digits);
  if (stat.ci_low === null || stat.ci_high === null) {
    return `${mean} (n=${stat.n})`;
  }
  return `${mean} [${stat.ci_low.toFixed(digits)}–${stat.ci_high.toFixed(digits)}] (n=${stat.n})`;
}

export function meanBy<T>(items: T[], key: (t: T) => number | null): number | null {
  const vals = items.map(key).filter((v): v is number => typeof v === "number");
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

export function groupBy<T, K extends string>(
  items: T[],
  key: (t: T) => K,
): Record<K, T[]> {
  const out = {} as Record<K, T[]>;
  for (const item of items) {
    const k = key(item);
    (out[k] ||= []).push(item);
  }
  return out;
}

export function fmt(v: number | null, digits = 2): string {
  return v === null ? "—" : v.toFixed(digits);
}
