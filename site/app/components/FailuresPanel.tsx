import type { FailureRow } from "@/lib/rollup";
import { fmt } from "@/lib/rollup";

/**
 * Surfaces individual completions whose score fell below the difficulty
 * threshold (easy < 0.9, medium < 0.7 by default — see analysis/rollup.py
 * `_FAILURE_THRESHOLDS`). Aggregate means hide the alarming-but-rare
 * cases; this panel makes them visible.
 *
 * Empty state is intentional and reassuring — "nothing to see here" is
 * a meaningful signal, not a layout bug.
 */
export function FailuresPanel({
  failures,
  thresholds,
}: {
  failures: FailureRow[];
  thresholds: Record<string, number>;
}) {
  if (failures.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 text-sm text-zinc-500 dark:text-zinc-400">
        No completions on this eval scored below the alarm threshold
        (easy &lt; {fmt(thresholds.easy ?? 0.9)}, medium &lt;{" "}
        {fmt(thresholds.medium ?? 0.7)}).
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {failures.map((f, i) => (
        <FailureCard key={`${f.task_id}-${f.provider}-${f.scorer}-${i}`} f={f} />
      ))}
    </div>
  );
}

function FailureCard({ f }: { f: FailureRow }) {
  return (
    <div className="rounded-lg border border-rose-200 dark:border-rose-900/50 bg-rose-50/40 dark:bg-rose-950/20 overflow-hidden">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-rose-200 dark:border-rose-900/50 bg-rose-100/60 dark:bg-rose-950/40 px-3 py-2 text-[11px] font-mono text-rose-700 dark:text-rose-300">
        <DifficultyChip difficulty={f.difficulty} />
        <span className="font-semibold">{f.task_id}</span>
        <span className="text-rose-600/80 dark:text-rose-400/80">
          {f.persona}
        </span>
        <span className="text-rose-600/80 dark:text-rose-400/80">
          {f.provider}
        </span>
        <span className="text-rose-600/80 dark:text-rose-400/80">
          {f.scorer}
        </span>
        <span className="ml-auto">
          score{" "}
          <strong className="tabular-nums">{fmt(f.score)}</strong>
          <span className="text-rose-500/70 dark:text-rose-400/60">
            {" "}
            (threshold {fmt(f.threshold)})
          </span>
        </span>
      </div>
      {f.explanation && (
        <p className="px-3 pt-3 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
          <span className="text-zinc-400 dark:text-zinc-500 font-mono mr-2">
            judge:
          </span>
          {f.explanation}
        </p>
      )}
      {f.completion && (
        <pre className="m-3 rounded border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-3 whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-zinc-700 dark:text-zinc-300 overflow-x-auto">
          {f.completion}
        </pre>
      )}
    </div>
  );
}

function DifficultyChip({ difficulty }: { difficulty: string }) {
  const colors: Record<string, string> = {
    easy: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400",
    medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    hard: "bg-rose-200 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
  };
  const cls = colors[difficulty] ?? "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono ${cls}`}>
      {difficulty}
    </span>
  );
}
