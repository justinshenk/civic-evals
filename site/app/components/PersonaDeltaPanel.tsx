import { fmt, groupBy, type RollupRow } from "@/lib/rollup";

/**
 * Surfaces persona-conditioned score variation on the eval detail page.
 *
 * Reader question: "for a given task, does the model give a different
 * answer when the asker's attributes change?" The aggregate per-eval
 * mean hides this — it averages over personas. This panel groups rows
 * by ``subdomain`` (which on persona-bearing evals like
 * ``policy_impact_personalization`` is the natural "same question,
 * different persona" key), shows the score per persona, and the
 * |Δscore| range.
 *
 * Sort by |Δ| desc so the tasks where persona swung the answer most
 * are at the top — those are the actionable cells for further
 * investigation.
 *
 * Filter: only shows subdomains that have ≥2 distinct personas in the
 * rollup. Otherwise there's nothing to compare. Empty state copy makes
 * that visible rather than hiding the panel entirely.
 */
export function PersonaDeltaPanel({
  rows,
  scorer,
}: {
  rows: RollupRow[];
  // Optional: restrict to one scorer (e.g. rubric_judge) so the
  // delta isn't averaged across measurement dimensions with different
  // semantics. When omitted, all scorers are pooled.
  scorer?: string;
}) {
  const filtered = scorer ? rows.filter((r) => r.scorer === scorer) : rows;
  const bySubdomain = groupBy(filtered, (r) => r.subdomain ?? "?");

  type Group = {
    subdomain: string;
    perPersona: { persona: string; provider: string; score: number }[];
    delta: number;
  };
  const groups: Group[] = [];

  for (const [subdomain, sdRows] of Object.entries(bySubdomain)) {
    const valid = sdRows.filter(
      (r): r is RollupRow & { score: number } => typeof r.score === "number",
    );
    const personas = new Set(valid.map((r) => r.persona));
    if (personas.size < 2) continue;

    const perPersona = valid
      .map((r) => ({
        persona: r.persona,
        provider: r.provider,
        score: r.score,
      }))
      .sort((a, b) => a.score - b.score);

    const min = perPersona[0]?.score ?? 0;
    const max = perPersona[perPersona.length - 1]?.score ?? 0;
    groups.push({ subdomain, perPersona, delta: max - min });
  }

  groups.sort((a, b) => b.delta - a.delta);

  if (groups.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 text-sm text-zinc-500 dark:text-zinc-400">
        No subdomain in this eval has ≥2 distinct personas in the
        rollup. Persona-conditioned variation is the headline metric
        for the interpretive track — when this panel is empty, the
        eval is either factual-track (one persona per task by design)
        or hasn't yet been run with persona variation.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={g.subdomain} className="panel">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-blue-200/60 dark:border-blue-400/15 bg-blue-50/70 dark:bg-blue-500/10">
            <span className="font-mono text-sm">{g.subdomain}</span>
            <span className="text-xs font-mono tabular-nums text-zinc-600 dark:text-zinc-400">
              |Δ| ={" "}
              <strong
                className={
                  g.delta >= 0.2
                    ? "text-rose-600 dark:text-rose-400"
                    : g.delta >= 0.1
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-zinc-700 dark:text-zinc-300"
                }
              >
                {fmt(g.delta)}
              </strong>
            </span>
          </div>
          <table className="w-full text-sm">
            <thead className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              <tr>
                <th className="px-4 py-1.5 text-left font-medium">persona</th>
                <th className="px-4 py-1.5 text-left font-medium">provider</th>
                <th className="px-4 py-1.5 text-right font-medium">score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-blue-100 dark:divide-blue-400/10">
              {g.perPersona.map((p, i) => (
                <tr key={`${p.persona}-${p.provider}-${i}`}>
                  <td className="px-4 py-1.5 font-mono text-xs">
                    {p.persona}
                  </td>
                  <td className="px-4 py-1.5 font-mono text-xs text-zinc-500 dark:text-zinc-400">
                    {p.provider}
                  </td>
                  <td className="px-4 py-1.5 text-right tabular-nums font-mono text-xs">
                    {fmt(p.score)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
