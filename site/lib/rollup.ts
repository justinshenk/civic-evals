import { readFileSync } from "node:fs";
import path from "node:path";

export type SubScores = {
  accuracy?: number;
  calibrated_uncertainty?: number;
  refusal_appropriateness?: number;
};

export type RollupRow = {
  eval: string;
  task_id: string;
  provider: string;
  persona: string;
  domain: string | null;
  subdomain: string | null;
  difficulty: string | null;
  tags: string;
  scorer: string;
  score: number | null;
  explanation: string;
  sub_scores: SubScores | null;
};

export type Rollup = {
  generated_at: string;
  n_rows: number;
  evals: string[];
  providers: string[];
  scorers: string[];
  rows: RollupRow[];
};

const EMPTY: Rollup = {
  generated_at: "",
  n_rows: 0,
  evals: [],
  providers: [],
  scorers: [],
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
