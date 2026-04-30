"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { type Rollup } from "@/lib/rollup-utils";
import { ProviderSelect, useProviderFilter } from "@/app/components/ProviderSelect";

type Props = { rollup: Rollup };

export function PersonaChart({ rollup }: Props) {
  const allRubricRows = rollup.rows.filter((r) => r.scorer === "rubric_judge");
  const { provider, setProvider, providers, filtered: rubricRows } = useProviderFilter(allRubricRows);

  const personas = [...new Set(rubricRows.map((r) => r.persona || "none"))].sort();
  const evals = [...new Set(rubricRows.map((r) => r.eval))].sort();

  const data = personas.map((persona) => {
    const row: Record<string, string | number> = { persona };
    for (const evalName of evals) {
      const scores = rubricRows
        .filter((r) => (r.persona || "none") === persona && r.eval === evalName)
        .map((r) => r.score)
        .filter((v): v is number => typeof v === "number");
      if (scores.length > 0) {
        row[evalName] = scores.reduce((a, b) => a + b, 0) / scores.length;
      }
    }
    return row;
  });

  const palette = ["#2563eb", "#16a34a", "#ea580c", "#9333ea", "#dc2626"];

  return (
    <div className="space-y-3">
      <ProviderSelect provider={provider} providers={providers} onChange={setProvider} />
      {rubricRows.length === 0 ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">No rubric_judge rows for this provider.</p>
      ) : (
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4">
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 12, right: 16, bottom: 12, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" vertical={false} />
                <XAxis dataKey="persona" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={60} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ fontSize: 12, borderRadius: 6 }}
                  formatter={(v) => (typeof v === "number" ? v.toFixed(2) : String(v))}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {evals.map((e, i) => (
                  <Bar key={e} dataKey={e} fill={palette[i % palette.length]} radius={[3, 3, 0, 0]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
