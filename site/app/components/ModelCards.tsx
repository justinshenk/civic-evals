import Link from "next/link";

import { fmt, meanBy, type Rollup } from "@/lib/rollup";

/**
 * Per-provider summary cards for the home page. Each card links to
 * ``/models/<provider>`` for the full model report card. The reader's
 * trust question — "should I rely on this model for civic info?" —
 * has model as the unit, not eval, so this view is the primary entry
 * point for that question.
 *
 * Hidden when no rollup rows exist (empty-state safety).
 */
export function ModelCards({ rollup }: { rollup: Rollup }) {
  if (rollup.providers.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        No models in the rollup yet.
      </p>
    );
  }
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {rollup.providers.map((provider) => (
        <ModelCard key={provider} provider={provider} rollup={rollup} />
      ))}
    </div>
  );
}

function ModelCard({
  provider,
  rollup,
}: {
  provider: string;
  rollup: Rollup;
}) {
  const rows = rollup.rows.filter((r) => r.provider === provider);
  const overall = meanBy(rows, (r) => r.score);
  const evalsCovered = new Set(rows.map((r) => r.eval)).size;
  const failures = rollup.failures.filter((f) => f.provider === provider);
  const hedged = failures.filter((f) => f.acknowledged_staleness === true).length;
  const noHedge = failures.filter((f) => f.acknowledged_staleness === false).length;

  return (
    <article className="card p-5 flex flex-col gap-3">
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="font-mono text-sm font-medium tracking-tight break-all">
          <Link
            href={`/models/${provider}`}
            className="text-blue-700 hover:underline decoration-blue-300 underline-offset-4 dark:text-blue-300"
          >
            {provider}
          </Link>
        </h3>
        <span
          className="shrink-0 rounded-full bg-blue-50 px-2 py-0.5 font-mono text-xs tabular-nums text-blue-700 dark:bg-blue-500/10 dark:text-blue-300"
          title="Average score across every test and grading method (0–1, higher is better)"
        >
          {overall === null ? "no runs" : `avg ${fmt(overall)}`}
        </span>
      </header>

      <dl className="grid grid-cols-3 gap-x-4 gap-y-2 text-xs">
        <div>
          <dt className="text-zinc-400 dark:text-zinc-500">Tests</dt>
          <dd className="font-mono tabular-nums">{evalsCovered}</dd>
        </div>
        <div>
          <dt className="text-zinc-400 dark:text-zinc-500">Answers</dt>
          <dd className="font-mono tabular-nums">{rows.length}</dd>
        </div>
        <div>
          <dt className="text-zinc-400 dark:text-zinc-500" title="Answers we flagged for a closer look">
            Flagged
          </dt>
          <dd className="font-mono tabular-nums">{failures.length}</dd>
        </div>
      </dl>

      {failures.length > 0 && (
        <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">
          Of {failures.length} flagged{" "}
          {failures.length === 1 ? "failure" : "failures"},{" "}
          <strong className="text-emerald-600 dark:text-emerald-400">
            {hedged}
          </strong>{" "}
          hedged{" "}
          {noHedge > 0 && (
            <>
              and{" "}
              <strong className="text-rose-600 dark:text-rose-400">
                {noHedge}
              </strong>{" "}
              were confidently wrong
            </>
          )}
          {noHedge === 0 && hedged === failures.length && (
            <span className="text-zinc-500"> — none confidently wrong</span>
          )}
          .
        </p>
      )}

      <footer className="pt-2 mt-auto text-xs">
        <Link
          href={`/models/${provider}`}
          className="font-medium text-blue-700 hover:text-blue-900 underline decoration-blue-300 underline-offset-3 dark:text-blue-300 dark:hover:text-blue-200"
        >
          report card →
        </Link>
      </footer>
    </article>
  );
}
