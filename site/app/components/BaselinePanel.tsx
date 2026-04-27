import {
  fmt,
  groupBy,
  meanBy,
  type ExternalBaseline,
  type Rollup,
  type RollupRow,
} from "@/lib/rollup";

/**
 * External baselines from UKGovernmentBEIS/inspect_evals.
 *
 * Run with --limit at refresh time, so the numbers aren't published-quality
 * — they're a comparison axis. The point is "civic eval scored X; same
 * model on TruthfulQA scored Y," not "we replicate the leaderboard."
 */
export function BaselinePanel({ rollup }: { rollup: Rollup }) {
  const baselines = rollup.external_baselines ?? [];

  if (baselines.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        No external baselines yet — run an inspect_evals task to populate.
      </p>
    );
  }

  const baselineRows = rollup.rows.filter((r) =>
    r.eval.startsWith("inspect_evals/"),
  );
  const byEvalProvider = groupBy(
    baselineRows,
    (r) => `${r.eval}::${r.provider}`,
  );

  return (
    <div className="space-y-4">
      {baselines.map((b) => (
        <BaselineCard
          key={b.name}
          baseline={b}
          byEvalProvider={byEvalProvider}
        />
      ))}
    </div>
  );
}

function BaselineCard({
  baseline,
  byEvalProvider,
}: {
  baseline: ExternalBaseline;
  byEvalProvider: Record<string, RollupRow[]>;
}) {
  return (
    <article className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 space-y-3">
      <header className="flex items-baseline justify-between gap-3">
        <div className="space-y-0.5">
          <h3 className="font-mono text-sm font-medium tracking-tight">
            {baseline.title}
          </h3>
          <p className="text-[11px] font-mono text-zinc-400 dark:text-zinc-500">
            {baseline.source} · {baseline.name}
          </p>
        </div>
        {baseline.arxiv && (
          <a
            href={baseline.arxiv}
            className="text-xs text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 underline decoration-zinc-300 dark:decoration-zinc-700 underline-offset-3"
          >
            paper →
          </a>
        )}
      </header>

      <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
        {baseline.description}
      </p>

      <div className="flex flex-wrap gap-3 pt-1 text-xs">
        {baseline.providers.length === 0 ? (
          <span className="text-zinc-400">no runs yet</span>
        ) : (
          baseline.providers.map((provider) => {
            const rows = byEvalProvider[`${baseline.name}::${provider}`] ?? [];
            const m = meanBy(rows, (r) => r.score);
            return (
              <div
                key={provider}
                className="rounded border border-zinc-200 dark:border-zinc-800 px-3 py-1.5"
              >
                <div className="text-[10px] font-mono text-zinc-400 dark:text-zinc-500">
                  {provider}
                </div>
                <div className="font-mono tabular-nums text-zinc-900 dark:text-zinc-100">
                  {fmt(m)}{" "}
                  <span className="text-[10px] text-zinc-400 dark:text-zinc-500">
                    n={rows.length}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </article>
  );
}
