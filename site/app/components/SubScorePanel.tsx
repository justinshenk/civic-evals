"use client";

import { fmt, meanBy, type Rollup } from "@/lib/rollup-utils";
import { ProviderSelect, useProviderFilter } from "@/app/components/ProviderSelect";

const DIMENSIONS = [
  { key: "accuracy", label: "Gets it right" },
  { key: "calibrated_uncertainty", label: "Honest about uncertainty" },
  { key: "refusal_appropriateness", label: "Refuses only when it should" },
] as const;

export function SubScorePanel({ rollup }: { rollup: Rollup }) {
  const allRubricRows = rollup.rows.filter((r) => r.scorer === "rubric_judge" && r.sub_scores);
  const { provider, setProvider, providers, filtered: rubricRows } = useProviderFilter(allRubricRows);

  const evals = [...new Set(rubricRows.map((r) => r.eval))].sort();

  return (
    <div className="space-y-3">
      <ProviderSelect provider={provider} providers={providers} onChange={setProvider} />
      {rubricRows.length === 0 ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">No graded answers for this model yet.</p>
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
          <div key={dim.key} className="card p-5 space-y-3">
            <div className="flex items-baseline justify-between">
              <h3 className="font-medium">{dim.label}</h3>
              <span className="ombre-text font-mono text-lg font-semibold tabular-nums">
                {fmt(overall)}
              </span>
            </div>
            <ul className="space-y-1.5">
              {perEval.map((pe) => (
                <li
                  key={pe.eval}
                  className="flex items-center justify-between gap-3 text-sm text-zinc-600 dark:text-zinc-400"
                >
                  <span className="min-w-0 truncate font-mono text-xs" title={pe.eval}>
                    {pe.eval}
                  </span>
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
    <span className="flex shrink-0 items-center gap-2">
      <span className="h-1.5 w-24 rounded-full bg-blue-100 dark:bg-blue-500/15 overflow-hidden">
        <span
          className="ombre-fill-h block h-full rounded-full"
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="font-mono text-xs tabular-nums w-10 text-right">{fmt(value)}</span>
    </span>
  );
}
