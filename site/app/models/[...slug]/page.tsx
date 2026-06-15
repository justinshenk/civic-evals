import Link from "next/link";
import { notFound } from "next/navigation";

import { FailuresPanel } from "@/app/components/FailuresPanel";
import { fmt, groupBy, loadRollup, meanBy } from "@/lib/rollup";
import { evalTitle } from "@/lib/evalCopy";

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
            className="font-medium text-blue-700 hover:text-blue-900 underline decoration-blue-300 underline-offset-3 dark:text-blue-300 dark:hover:text-blue-200"
          >
            ← all models
          </Link>
        </nav>

        <header className="space-y-3">
          <p className="inline-flex items-center gap-2 rounded-full border border-blue-200/70 bg-blue-50/70 px-3 py-1 text-xs font-medium uppercase tracking-widest text-blue-700 dark:border-blue-400/20 dark:bg-blue-500/10 dark:text-blue-300">
            CORDA · P3 · model report card
          </p>
          <h1 className="font-mono text-3xl font-semibold tracking-tight break-all ombre-text">
            {provider}
          </h1>
          <p className="max-w-3xl text-lg text-zinc-600 dark:text-zinc-300 leading-relaxed">
            How <code className="font-mono text-base">{provider}</code> did across every test in the
            suite. The tables below show where it&rsquo;s strong or weak; the last section collects
            the answers worth a closer look — and whether the model admitted it might be wrong.
          </p>
          <div className="flex flex-wrap gap-x-6 gap-y-2 pt-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">
                {evalRows.length}
              </strong>{" "}
              tests
            </span>
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">
                {rows.length}
              </strong>{" "}
              answers graded
            </span>
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">
                {failures.length}
              </strong>{" "}
              flagged
            </span>
            <span>
              average score{" "}
              <strong className="text-zinc-900 dark:text-zinc-100">
                {fmt(overall)}
              </strong>
            </span>
          </div>
        </header>

        <section className="space-y-3">
          <SectionHeader
            title="Score on each test"
            hint="This model's average score on every test, highest to lowest. Click a test to open it."
          />
          <SummaryTable rows={evalRows} unit="test" linkPrefix="/evals" />
        </section>

        <section className="space-y-3">
          <SectionHeader
            title="Strengths and weaknesses"
            hint="The same answers, averaged by what each grading method measures — so you can see what this model is good at and where it slips."
          />
          <SummaryTable rows={scorerRows} unit="grading method" />
        </section>

        <section className="space-y-3">
          <SectionHeader
            title="Worth a closer look"
            hint="The answers this model got wrong enough to flag. The ones to worry about most are where it was confidently wrong — no hint that it might be out of date or that you should check an official source."
            details={`Flagged when an answer scores below a per-difficulty alarm bar (easy < ${fmt(thresholds.easy ?? 0.9)}, medium < ${fmt(thresholds.medium ?? 0.7)}). "Hedged" = the model flagged possible staleness or pointed at an authoritative source; "no hedge" = confidently wrong.`}
          />
          <FailuresPanel
            failures={failures}
            thresholds={thresholds}
            summary={failureSummary}
          />
        </section>

        <footer className="pt-8 border-t border-blue-200/60 dark:border-blue-400/15 text-sm text-zinc-500 dark:text-zinc-400">
          <p>
            Aggregation source: every row in{" "}
            <Link
              href="https://github.com/justinshenk/civic-evals/blob/main/site/public/data/rollup.json"
              className="text-blue-700 underline decoration-blue-300 underline-offset-4 dark:text-blue-300"
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
    <div className="panel overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-blue-50/80 dark:bg-blue-500/10 text-left text-xs uppercase tracking-wider text-blue-900 dark:text-blue-200">
          <tr>
            <th className="px-3 py-2 font-medium">{unit}</th>
            <th className="px-3 py-2 font-medium text-right">answers</th>
            <th className="px-3 py-2 font-medium text-right">avg score</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-blue-100 dark:divide-blue-400/10">
          {rows.map((r) => (
            <tr key={r.name} className="transition-colors hover:bg-blue-50/50 dark:hover:bg-blue-500/5">
              <td className="px-3 py-2 text-xs">
                {linkPrefix ? (
                  <Link
                    href={`${linkPrefix}/${r.name}`}
                    className="font-medium text-blue-700 hover:underline decoration-blue-300 underline-offset-4 dark:text-blue-300"
                  >
                    {evalTitle(r.name)}
                  </Link>
                ) : (
                  <span className="font-mono">{r.name}</span>
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

function SectionHeader({
  title,
  hint,
  details,
}: {
  title: string;
  hint: string;
  details?: React.ReactNode;
}) {
  return (
    <header className="flex gap-3">
      <span aria-hidden className="ombre-rule mt-1 w-1 shrink-0 rounded-full" />
      <div className="space-y-2 max-w-3xl">
        <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">{title}</h2>
        <p className="text-[15px] text-zinc-600 dark:text-zinc-300 leading-relaxed">{hint}</p>
        {details && (
          <details className="group">
            <summary className="inline-flex w-fit cursor-pointer items-center gap-1.5 rounded-full border border-blue-200/70 bg-blue-50/60 px-2.5 py-1 text-xs font-medium text-blue-700 list-none [&::-webkit-details-marker]:hidden hover:bg-blue-100/70 dark:border-blue-400/20 dark:bg-blue-500/10 dark:text-blue-300 dark:hover:bg-blue-500/20">
              <span aria-hidden className="transition-transform group-open:rotate-90">
                ▸
              </span>
              Technical details
            </summary>
            <div className="mt-2 rounded-lg border border-blue-200/50 bg-blue-50/30 px-3 py-2.5 text-xs leading-relaxed text-zinc-600 dark:border-blue-400/15 dark:bg-blue-500/5 dark:text-zinc-400">
              {details}
            </div>
          </details>
        )}
      </div>
    </header>
  );
}

