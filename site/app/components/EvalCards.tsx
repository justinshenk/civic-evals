import Link from "next/link";
import { fmt, groupBy, meanBy, type Rollup, type EvalMeta } from "@/lib/rollup";
import { EVAL_COPY } from "@/lib/evalCopy";

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
  const plain = EVAL_COPY[meta.name];
  const title = plain?.title ?? meta.name;
  const summary = plain?.summary ?? meta.description ?? "No description provided.";

  return (
    <article className="card p-5 flex flex-col gap-3">
      <header className="flex items-start justify-between gap-3">
        <div className="space-y-0.5">
          <h3 className="text-base font-semibold tracking-tight leading-snug">
            <Link
              href={`/evals/${meta.name}`}
              className="text-blue-700 hover:underline decoration-blue-300 underline-offset-4 dark:text-blue-300"
            >
              {title}
            </Link>
          </h3>
          <p className="font-mono text-[10px] text-zinc-400 dark:text-zinc-500">{meta.name}</p>
        </div>
        <span
          className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 font-mono text-xs tabular-nums text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"
          title="Average score across every grading method and run (0–1, higher is better)"
        >
          {overall === null ? "no runs yet" : `avg ${fmt(overall)}`}
        </span>
      </header>

      <p className="text-sm text-zinc-600 dark:text-zinc-300 leading-relaxed">
        {summary}
      </p>

      <details className="group text-xs">
        <summary className="inline-flex w-fit cursor-pointer items-center gap-1.5 text-blue-700 list-none [&::-webkit-details-marker]:hidden hover:underline dark:text-blue-300">
          <span aria-hidden className="transition-transform group-open:rotate-90">
            ▸
          </span>
          Show test details
        </summary>
        <div className="mt-3 space-y-3">
          {plain && meta.description && (
            <p className="text-zinc-500 dark:text-zinc-400 leading-relaxed">
              <span className="font-medium text-zinc-600 dark:text-zinc-300">
                Full description:{" "}
              </span>
              {meta.description}
            </p>
          )}

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
            <div>
              <dt className="text-zinc-400 dark:text-zinc-500">Questions</dt>
              <dd className="font-mono tabular-nums">{meta.task_count}</dd>
            </div>
            <div>
              <dt className="text-zinc-400 dark:text-zinc-500">Types of asker</dt>
              <dd className="font-mono tabular-nums">{meta.personas_used.length}</dd>
            </div>
          </dl>

          <DifficultyBar difficulty={meta.difficulty} total={totalDiff} />

          <div className="flex flex-wrap gap-1">
            {meta.subdomains.slice(0, 6).map((s) => (
              <span
                key={s}
                className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-mono text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"
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

          <ScorerBadges kinds={meta.scorer_kinds} />
        </div>
      </details>

      <footer className="pt-2 mt-auto flex items-center justify-end text-xs">
        <Link
          href={`/evals/${meta.name}`}
          className="font-medium text-blue-700 hover:text-blue-900 underline decoration-blue-300 underline-offset-3 dark:text-blue-300 dark:hover:text-blue-200"
        >
          View questions &amp; results →
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
          className="inline-flex items-center rounded-full border border-blue-200 dark:border-blue-400/25 px-2 py-0.5 text-[10px] font-mono text-blue-700 dark:text-blue-300"
          title={k === "rubric" ? "scored by LLM judge with rubric" : "scored by ground-truth match"}
        >
          {k}
        </span>
      ))}
    </div>
  );
}
