import Link from "next/link";
import { notFound } from "next/navigation";

import { FailuresPanel } from "@/app/components/FailuresPanel";
import { fmt, groupBy, loadRollup, meanBy } from "@/lib/rollup";

/**
 * Per-model report card.
 *
 * Reader question: "should I rely on this model for civic information?"
 * That's harder to answer from the per-eval pages — those organize the
 * data by what's being measured, not by who's being measured. This
 * page flips the axis: one model, all evals, with the same
 * refusal-shaped / staleness-hedge framing the per-eval pages use.
 *
 * Catch-all dynamic segment ``[...slug]`` so provider IDs containing
 * slashes (``anthropic/claude-sonnet-4-6``) round-trip cleanly through
 * the URL without encoding gymnastics. ``params.slug`` arrives as
 * ``["anthropic", "claude-sonnet-4-6"]`` and we re-join.
 *
 * Failure surfacing is reused from the per-eval page (FailuresPanel)
 * because the contract is identical — the panel cares about a list of
 * FailureRow, not about which axis selected the list.
 */
export function generateStaticParams() {
  return loadRollup().providers.map((provider) => ({
    slug: provider.split("/"),
  }));
}

export default async function ModelPage({
  params,
}: {
  params: Promise<{ slug: string[] }>;
}) {
  const { slug } = await params;
  const provider = slug.join("/");
  const rollup = loadRollup();
  if (!rollup.providers.includes(provider)) notFound();

  const rows = rollup.rows.filter((r) => r.provider === provider);
  const overall = meanBy(rows, (r) => r.score);
  const failures = rollup.failures.filter((f) => f.provider === provider);
  const thresholds = rollup.failure_thresholds ?? {};

  // Per-eval mean. The site's headline number per eval × this model.
  const byEval = groupBy(rows, (r) => r.eval);
  const evalRows = Object.entries(byEval)
    .map(([name, rs]) => ({
      name,
      n_rows: rs.length,
      mean: meanBy(rs, (r) => r.score),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  // Per-scorer mean. Tells the reader where this model is strong or
  // weak across the suite's measurement dimensions, in one table.
  const byScorer = groupBy(rows, (r) => r.scorer);
  const scorerRows = Object.entries(byScorer)
    .map(([name, rs]) => ({
      name,
      n_rows: rs.length,
      mean: meanBy(rs, (r) => r.score),
    }))
    .sort((a, b) => a.name.localeCompare(b.name));

  // Construct a synthetic FailureSummaryRow scoped to this provider so
  // the StalenessSummary banner renders the same shape as on the
  // per-eval pages.
  const ack = failures.filter((f) => f.acknowledged_staleness === true).length;
  const noAck = failures.filter((f) => f.acknowledged_staleness === false).length;
  const failureSummary =
    failures.length > 0
      ? {
          eval: provider,
          n_failures: failures.length,
          n_acknowledged: ack,
          n_unacknowledged: noAck,
          ack_rate: failures.length > 0 ? ack / failures.length : null,
        }
      : undefined;

  return (
    <main className="flex-1 w-full">
      <div className="mx-auto max-w-6xl px-6 py-12 space-y-10">
        <nav className="text-sm">
          <Link
            href="/"
            className="text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 underline decoration-zinc-300 dark:decoration-zinc-700 underline-offset-3"
          >
            ← all models
          </Link>
        </nav>

        <header className="space-y-3">
          <p className="text-xs uppercase tracking-widest text-zinc-500 dark:text-zinc-400">
            CORDA · P3 · model report card
          </p>
          <h1 className="font-mono text-3xl font-semibold tracking-tight break-all">
            {provider}
          </h1>
          <p className="max-w-3xl text-zinc-600 dark:text-zinc-400 leading-relaxed">
            Aggregated performance of{" "}
            <code className="font-mono">{provider}</code> across every
            eval in the suite. Use the per-eval table below to see where
            this model is strong or weak; use the failures section to
            see where it gets things wrong, and whether it knew it was
            wrong.
          </p>
          <div className="flex flex-wrap gap-6 pt-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">
                {evalRows.length}
              </strong>{" "}
              evals
            </span>
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">
                {rows.length}
              </strong>{" "}
              rows
            </span>
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">
                {failures.length}
              </strong>{" "}
              flagged
            </span>
            <span>
              overall mean{" "}
              <strong className="text-zinc-900 dark:text-zinc-100">
                {fmt(overall)}
              </strong>
            </span>
          </div>
        </header>

        <section className="space-y-3">
          <SectionHeader
            title="Per-eval mean"
            hint="Mean of all scorers, all rows, this model on each eval."
          />
          <SummaryTable rows={evalRows} unit="eval" linkPrefix="/evals" />
        </section>

        <section className="space-y-3">
          <SectionHeader
            title="Per-scorer mean"
            hint="Mean across all evals on each measurement dimension. Tells you where this model is strong or weak in the suite's scoring axes."
          />
          <SummaryTable rows={scorerRows} unit="scorer" />
        </section>

        <section className="space-y-3">
          <SectionHeader
            title="Worth a closer look"
            hint={`This model's flagged failures (easy < ${fmt(thresholds.easy ?? 0.9)}, medium < ${fmt(thresholds.medium ?? 0.7)}). Hedged = the model knew its training data may be stale or pointed at a source; no-hedge = confidently wrong.`}
          />
          <FailuresPanel
            failures={failures}
            thresholds={thresholds}
            summary={failureSummary}
          />
        </section>

        <footer className="pt-8 border-t border-zinc-200 dark:border-zinc-800 text-sm text-zinc-500 dark:text-zinc-400">
          <p>
            Aggregation source: every row in{" "}
            <Link
              href="https://github.com/justinshenk/civic-evals/blob/main/site/public/data/rollup.json"
              className="underline decoration-zinc-400 underline-offset-4"
            >
              rollup.json
            </Link>{" "}
            with provider = <code className="font-mono">{provider}</code>.
          </p>
        </footer>
      </div>
    </main>
  );
}

function SummaryTable({
  rows,
  unit,
  linkPrefix,
}: {
  rows: { name: string; n_rows: number; mean: number | null }[];
  unit: string;
  linkPrefix?: string;
}) {
  if (rows.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        No {unit} data for this model.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-sm">
        <thead className="bg-zinc-50 dark:bg-zinc-900/40 text-left text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
          <tr>
            <th className="px-3 py-2 font-medium">{unit}</th>
            <th className="px-3 py-2 font-medium text-right">rows</th>
            <th className="px-3 py-2 font-medium text-right">mean</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {rows.map((r) => (
            <tr key={r.name} className="bg-white dark:bg-zinc-950">
              <td className="px-3 py-2 font-mono text-xs">
                {linkPrefix ? (
                  <Link
                    href={`${linkPrefix}/${r.name}`}
                    className="hover:underline decoration-zinc-400 underline-offset-4"
                  >
                    {r.name}
                  </Link>
                ) : (
                  r.name
                )}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{r.n_rows}</td>
              <td className="px-3 py-2 text-right">
                <ScoreCell score={r.mean} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ScoreCell({ score }: { score: number | null }) {
  if (score === null) return <span className="text-zinc-400">—</span>;
  let color = "text-zinc-600 dark:text-zinc-400";
  if (score >= 0.85) color = "text-emerald-600 dark:text-emerald-400";
  else if (score >= 0.6) color = "text-amber-600 dark:text-amber-400";
  else color = "text-rose-600 dark:text-rose-400";
  return (
    <span className={`tabular-nums font-mono ${color}`}>{fmt(score)}</span>
  );
}

function SectionHeader({ title, hint }: { title: string; hint: string }) {
  return (
    <header className="space-y-1">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-3xl">
        {hint}
      </p>
    </header>
  );
}

