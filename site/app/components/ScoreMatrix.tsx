"use client";

import {
  cellStatLookup,
  fmt,
  fmtMeanCI,
  groupBy,
  meanBy,
  type Rollup,
} from "@/lib/rollup-utils";
import { ProviderSelect, useProviderFilter } from "@/app/components/ProviderSelect";
import { evalTitle } from "@/lib/evalCopy";

export function ScoreMatrix({ rollup }: { rollup: Rollup }) {
  const { provider, setProvider, providers, filtered: filteredRows } = useProviderFilter(rollup.rows);

  const byEval = groupBy(filteredRows, (r) => r.eval);
  const evalsSorted = [...rollup.evals].sort();
  const scorersSorted = [...rollup.scorers].sort();

  // The bootstrap-CI lookup keys on (eval, scorer, provider) — when
  // the user hasn't filtered to a single provider, fall back to the
  // un-bucketed mean (no CI surfaced because we'd be averaging across
  // providers with potentially different sample sizes).
  const stat = cellStatLookup(rollup.cell_stats);

  return (
    <div className="space-y-3">
      <ProviderSelect provider={provider} providers={providers} onChange={setProvider} />
      <div className="panel overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-blue-50/80 dark:bg-blue-500/10 text-blue-900 dark:text-blue-200">
          <tr>
            <th className="text-left font-medium px-4 py-3">Test</th>
            {scorersSorted.map((s) => (
              <th key={s} className="text-right font-medium px-4 py-3 font-mono text-xs">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-blue-100 dark:divide-blue-400/10">
          {evalsSorted.map((e) => {
            const rows = byEval[e] ?? [];
            const byScorer = groupBy(rows, (r) => r.scorer);
            return (
              <tr key={e} className="transition-colors hover:bg-blue-50/50 dark:hover:bg-blue-500/5">
                <td className="px-4 py-3 text-sm font-medium" title={e}>
                  {evalTitle(e)}
                </td>
                {scorersSorted.map((s) => {
                  const cell = byScorer[s] ?? [];
                  const m = meanBy(cell, (r) => r.score);
                  // Bootstrap CI only when the user has filtered to
                  // one provider — otherwise the cell aggregates
                  // across providers and the per-cell CI would
                  // misrepresent.
                  const cs =
                    provider !== "All Providers"
                      ? stat(e, s, provider)
                      : undefined;
                  const tooltip = cs
                    ? fmtMeanCI(cs)
                    : `${cell.length} sample${cell.length === 1 ? "" : "s"}`;
                  return (
                    <td
                      key={s}
                      className="px-4 py-3 text-right font-mono tabular-nums"
                      title={tooltip}
                    >
                      <ScoreBadge value={m} stat={cs} />
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

type CSLite = { ci_low: number | null; ci_high: number | null; n: number } | undefined;

function ScoreBadge({ value, stat }: { value: number | null; stat?: CSLite }) {
  if (value === null) return <span className="text-zinc-400">—</span>;
  const pct = Math.round(value * 100);
  const hue = Math.round(value * 120); // red-to-green
  // Width of the 95% CI as a faint label below the badge. With N=5–15
  // per cell after persona expansion, the spread is the more honest
  // signal than the point estimate alone — a half-point CI on a 0.05
  // delta tells the reader the delta is noise.
  const ciSpan =
    stat && stat.ci_low !== null && stat.ci_high !== null
      ? stat.ci_high - stat.ci_low
      : null;
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <span
        className="inline-block rounded px-2 py-0.5 text-xs font-mono"
        style={{
          backgroundColor: `hsl(${hue} 70% 92%)`,
          color: `hsl(${hue} 60% 25%)`,
        }}
      >
        {fmt(value)} <span className="opacity-60">({pct}%)</span>
      </span>
      {stat && (
        <span className="text-[10px] font-mono text-zinc-500 dark:text-zinc-400 tabular-nums">
          {ciSpan !== null ? `±${(ciSpan / 2).toFixed(2)} ` : ""}
          n={stat.n}
        </span>
      )}
    </span>
  );
}
