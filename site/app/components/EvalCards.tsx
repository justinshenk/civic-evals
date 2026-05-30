import Link from "next/link";
import { fmt, groupBy, meanBy, type Rollup, type EvalMeta } from "@/lib/rollup";

export function EvalCards({ rollup }: { rollup: Rollup }) {
  const byEval = groupBy(rollup.rows, (r) => r.eval);

  if (rollup.evals_meta.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        No evals registered yet.
      </p>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {rollup.evals_meta.map((meta) => (
        <EvalCard key={meta.name} meta={meta} rows={byEval[meta.name] ?? []} />
      ))}
    </div>
  );
}

function EvalCard({ meta, rows }: { meta: EvalMeta; rows: Rollup["rows"] }) {
  const overall = meanBy(rows, (r) => r.score);
  const totalDiff = Object.values(meta.difficulty).reduce((a, b) => a + b, 0) || 1;

  return (
    <article className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-5 flex flex-col gap-3 hover:border-zinc-400 dark:hover:border-zinc-600 transition-colors">
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="font-mono text-sm font-medium tracking-tight">
          <Link
            href={`/evals/${meta.name}`}
            className="hover:underline decoration-zinc-400 underline-offset-4"
          >
            {meta.name}
          </Link>
        </h3>
        <span
          className="font-mono text-xs tabular-nums text-zinc-500 dark:text-zinc-400"
          title="mean of all scorers, all rows"
        >
          {overall === null ? "no runs yet" : `mean ${fmt(overall)}`}
        </span>
      </header>

      <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed line-clamp-4">
        {meta.description || "No description provided."}
      </p>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <dt className="text-zinc-400 dark:text-zinc-500">Tasks</dt>
          <dd className="font-mono tabular-nums">{meta.task_count}</dd>
        </div>
        <div>
          <dt className="text-zinc-400 dark:text-zinc-500">Personas</dt>
          <dd className="font-mono tabular-nums">{meta.personas_used.length}</dd>
        </div>
      </dl>

      <DifficultyBar difficulty={meta.difficulty} total={totalDiff} />

      <div className="flex flex-wrap gap-1">
        {meta.subdomains.slice(0, 6).map((s) => (
          <span
            key={s}
            className="inline-flex items-center rounded bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-600 dark:text-zinc-300"
          >
            {s}
          </span>
        ))}
        {meta.subdomains.length > 6 && (
          <span className="text-[10px] text-zinc-400">
            +{meta.subdomains.length - 6} more
          </span>
        )}
      </div>

      <footer className="pt-2 mt-auto flex items-center justify-between text-xs">
        <ScorerBadges kinds={meta.scorer_kinds} />
        <Link
          href={`/evals/${meta.name}`}
          className="text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 underline decoration-zinc-300 dark:decoration-zinc-700 underline-offset-3"
        >
          tasks →
        </Link>
      </footer>
    </article>
  );
}

function DifficultyBar({
  difficulty,
  total,
}: {
  difficulty: Record<string, number>;
  total: number;
}) {
  const order: Array<["easy" | "medium" | "hard", string]> = [
    ["easy", "bg-emerald-500"],
    ["medium", "bg-amber-500"],
    ["hard", "bg-rose-500"],
  ];
  return (
    <div className="space-y-1.5">
      <div className="flex h-1.5 rounded-full overflow-hidden bg-zinc-100 dark:bg-zinc-800">
        {order.map(([key, color]) => {
          const n = difficulty[key] ?? 0;
          const pct = (n / total) * 100;
          if (pct === 0) return null;
          return <span key={key} className={`block h-full ${color}`} style={{ width: `${pct}%` }} />;
        })}
      </div>
      <div className="flex gap-3 text-[10px] text-zinc-500 dark:text-zinc-400 font-mono">
        {order.map(([key]) => (
          <span key={key}>
            {key} {difficulty[key] ?? 0}
          </span>
        ))}
      </div>
    </div>
  );
}

function ScorerBadges({ kinds }: { kinds: string[] }) {
  return (
    <div className="flex gap-1">
      {kinds.map((k) => (
        <span
          key={k}
          className="inline-flex items-center rounded border border-zinc-200 dark:border-zinc-700 px-1.5 py-0.5 text-[10px] font-mono text-zinc-600 dark:text-zinc-400"
          title={k === "rubric" ? "scored by LLM judge with rubric" : "scored by ground-truth match"}
        >
          {k}
        </span>
      ))}
    </div>
  );
}
