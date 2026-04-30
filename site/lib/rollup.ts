import { readFileSync } from "node:fs";
import path from "node:path";

export type {
  SubScores,
  PersonaAttrs,
  ScoreDiagnostics,
  RollupRow,
  TaskSummary,
  EvalMeta,
  CalibrationStat,
  ExternalBaseline,
  Rollup,
} from "@/lib/rollup-utils";
export { meanBy, groupBy, fmt } from "@/lib/rollup-utils";

import type { Rollup } from "@/lib/rollup-utils";

const EMPTY: Rollup = {
  generated_at: "",
  n_rows: 0,
  evals: [],
  providers: [],
  scorers: [],
  evals_meta: [],
  calibration_stats: [],
  external_baselines: [],
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
