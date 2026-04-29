"use client";

import { useState } from "react";
import { fmt, groupBy, meanBy, type Rollup } from "@/lib/rollup-utils";
import { ProviderSelect } from "@/app/components/ProviderSelect";

export function ScoreMatrix({ rollup }: { rollup: Rollup }) {
  const [provider, setProvider] = useState<string>("All Providers");

  const providersWithData = [...new Set(rollup.rows.map((r) => r.provider))].sort();

  const filteredRows =
    provider === "All Providers"
      ? rollup.rows
      : rollup.rows.filter((r) => r.provider === provider);

  const byEval = groupBy(filteredRows, (r) => r.eval);
  const evalsSorted = [...rollup.evals].sort();
  const scorersSorted = [...rollup.scorers].sort();

  return (
    <div className="space-y-3">
      <ProviderSelect id="score-matrix-provider" provider={provider} providers={providersWithData} onChange={setProvider} />
      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-sm">
        <thead className="bg-zinc-100 dark:bg-zinc-900 text-zinc-600 dark:text-zinc-400">
          <tr>
            <th className="text-left font-medium px-4 py-3">Eval</th>
            {scorersSorted.map((s) => (
              <th key={s} className="text-right font-medium px-4 py-3 font-mono text-xs">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {evalsSorted.map((e) => {
            const rows = byEval[e] ?? [];
            const byScorer = groupBy(rows, (r) => r.scorer);
            return (
              <tr key={e}>
                <td className="px-4 py-3 font-mono text-sm">{e}</td>
                {scorersSorted.map((s) => {
                  const cell = byScorer[s] ?? [];
                  const m = meanBy(cell, (r) => r.score);
                  return (
                    <td
                      key={s}
                      className="px-4 py-3 text-right font-mono tabular-nums"
                      title={`${cell.length} sample${cell.length === 1 ? "" : "s"}`}
                    >
                      <ScoreBadge value={m} />
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
    </div>
  );
}

function ScoreBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-zinc-400">—</span>;
  const pct = Math.round(value * 100);
  const hue = Math.round(value * 120); // red-to-green
  return (
    <span
      className="inline-block rounded px-2 py-0.5 text-xs font-mono"
      style={{
        backgroundColor: `hsl(${hue} 70% 92%)`,
        color: `hsl(${hue} 60% 25%)`,
      }}
    >
      {fmt(value)} <span className="opacity-60">({pct}%)</span>
    </span>
  );
}
