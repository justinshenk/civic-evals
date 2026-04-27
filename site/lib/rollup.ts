import { readFileSync } from "node:fs";
import path from "node:path";

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
};

export type EvalMeta = {
  name: string;
  description: string;
  task_count: number;
  difficulty: Record<string, number>;
  subdomains: string[];
  personas_used: string[];
  scorer_kinds: string[];
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

export type Rollup = {
  generated_at: string;
  n_rows: number;
  evals: string[];
  providers: string[];
  scorers: string[];
  evals_meta: EvalMeta[];
  calibration_stats: CalibrationStat[];
  rows: RollupRow[];
};

const EMPTY: Rollup = {
  generated_at: "",
  n_rows: 0,
  evals: [],
  providers: [],
  scorers: [],
  evals_meta: [],
  calibration_stats: [],
  rows: [],
};

export function loadRollup(): Rollup {
  const file = path.join(process.cwd(), "public", "data", "rollup.json");
  try {
    const text = readFileSync(file, "utf8");
    return JSON.parse(text) as Rollup;
  } catch {
    return EMPTY;
  }
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
