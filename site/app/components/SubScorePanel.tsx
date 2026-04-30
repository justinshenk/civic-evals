"use client";

import { fmt, meanBy, type Rollup } from "@/lib/rollup-utils";
import { ProviderSelect, useProviderFilter } from "@/app/components/ProviderSelect";

const DIMENSIONS = [
  { key: "accuracy", label: "Accuracy" },
  { key: "calibrated_uncertainty", label: "Calibrated uncertainty" },
  { key: "refusal_appropriateness", label: "Appropriate refusal" },
] as const;

export function SubScorePanel({ rollup }: { rollup: Rollup }) {
  const allRubricRows = rollup.rows.filter((r) => r.scorer === "rubric_judge" && r.sub_scores);
  const { provider, setProvider, providers, filtered: rubricRows } = useProviderFilter(allRubricRows);

  const evals = [...new Set(rubricRows.map((r) => r.eval))].sort();

  return (
    <div className="space-y-3">
      <ProviderSelect provider={provider} providers={providers} onChange={setProvider} />
      {rubricRows.length === 0 ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">No rubric_judge runs for this provider.</p>
      ) : (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {DIMENSIONS.map((dim) => {
        const rows = rubricRows.map((r) => ({
          eval: r.eval,
          value: r.sub_scores?.[dim.key] ?? null,
        }));
        const overall = meanBy(rows, (r) => r.value);
        const perEval = evals.map((e) => ({
          eval: e,
          mean: meanBy(
            rows.filter((r) => r.eval === e),
            (r) => r.value,
          ),
        }));
        return (
          <div
            key={dim.key}
            className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-3"
          >
            <div className="flex items-baseline justify-between">
              <h3 className="font-medium">{dim.label}</h3>
              <span className="font-mono text-lg tabular-nums">{fmt(overall)}</span>
            </div>
            <ul className="space-y-1.5">
              {perEval.map((pe) => (
                <li
                  key={pe.eval}
                  className="flex items-center justify-between text-sm text-zinc-600 dark:text-zinc-400"
                >
                  <span className="font-mono text-xs">{pe.eval}</span>
                  <Bar value={pe.mean} />
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      </div>
      )}
    </div>
  );
}

function Bar({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="font-mono text-xs text-zinc-400">—</span>;
  }
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-24 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
        <span
          className="block h-full bg-emerald-500"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="font-mono text-xs tabular-nums w-10 text-right">{fmt(value)}</span>
    </span>
  );
}
