import { notFound } from "next/navigation";
import Link from "next/link";
import { FailuresPanel } from "@/app/components/FailuresPanel";
import { FermiRangeBar } from "@/app/components/FermiRangeBar";
import { MethodsPanel } from "@/app/components/MethodsPanel";
import { PersonaDeltaPanel } from "@/app/components/PersonaDeltaPanel";
import {
  fmt,
  groupBy,
  loadRollup,
  meanBy,
  type RollupRow,
  type TaskSummary,
} from "@/lib/rollup";
import { EVAL_COPY } from "@/lib/evalCopy";

export function generateStaticParams() {
  return loadRollup().evals_meta.map((m) => ({ name: m.name }));
}

export default async function EvalPage({ params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  const rollup = loadRollup();
  const meta = rollup.evals_meta.find((m) => m.name === name);
  if (!meta) notFound();

  const evalRows = rollup.rows.filter((r) => r.eval === name);
  const overall = meanBy(evalRows, (r) => r.score);
  const byTask = groupBy(evalRows, (r) => r.task_id);
  const scorers = Array.from(new Set(evalRows.map((r) => r.scorer))).sort();
  const failures = (rollup.failures ?? []).filter((f) => f.eval === name);
  const thresholds = rollup.failure_thresholds ?? {};
  const failureSummary = rollup.failure_summary?.by_eval?.find(
    (r) => r.eval === name,
  );

  const plain = EVAL_COPY[meta.name];
  const title = plain?.title ?? meta.name;
  const summary = plain?.summary ?? meta.description ?? "No description provided.";

  return (
    <main className="flex-1 w-full">
      <div className="mx-auto max-w-6xl px-6 py-12 space-y-10">
        <nav className="text-sm">
          <Link
            href="/"
            className="font-medium text-blue-700 hover:text-blue-900 underline decoration-blue-300 underline-offset-3 dark:text-blue-300 dark:hover:text-blue-200"
          >
            ← all evals
          </Link>
        </nav>

        <header className="space-y-3">
          <p className="inline-flex items-center gap-2 rounded-full border border-blue-200/70 bg-blue-50/70 px-3 py-1 text-xs font-medium uppercase tracking-widest text-blue-700 dark:border-blue-400/20 dark:bg-blue-500/10 dark:text-blue-300">
            CORDA · P3 · one test
          </p>
          <div className="space-y-1">
            <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight ombre-text">{title}</h1>
            <p className="font-mono text-xs text-zinc-400 dark:text-zinc-500">{meta.name}</p>
          </div>
          <p className="max-w-3xl text-lg text-zinc-600 dark:text-zinc-300 leading-relaxed">
            {summary}
          </p>
          {plain && meta.description && (
            <details className="group max-w-3xl">
              <summary className="inline-flex w-fit cursor-pointer items-center gap-1.5 rounded-full border border-blue-200/70 bg-blue-50/60 px-2.5 py-1 text-xs font-medium text-blue-700 list-none [&::-webkit-details-marker]:hidden hover:bg-blue-100/70 dark:border-blue-400/20 dark:bg-blue-500/10 dark:text-blue-300 dark:hover:bg-blue-500/20">
                <span aria-hidden className="transition-transform group-open:rotate-90">
                  ▸
                </span>
                Full description
              </summary>
              <p className="mt-2 rounded-lg border border-blue-200/50 bg-blue-50/30 px-3 py-2.5 text-sm leading-relaxed text-zinc-600 dark:border-blue-400/15 dark:bg-blue-500/5 dark:text-zinc-400">
                {meta.description}
              </p>
            </details>
          )}
          <div className="flex flex-wrap gap-x-6 gap-y-2 pt-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">{meta.task_count}</strong>{" "}
              questions
            </span>
            <span>
              graded{" "}
              <strong className="text-zinc-900 dark:text-zinc-100">{scorers.length}</strong>{" "}
              {scorers.length === 1 ? "way" : "ways"}
            </span>
            <span>
              average score{" "}
              <strong className="text-zinc-900 dark:text-zinc-100">{fmt(overall)}</strong>
            </span>
            <a
              href={meta.readme_url}
              className="font-medium text-blue-700 underline decoration-blue-300 underline-offset-4 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-200"
            >
              full README →
            </a>
          </div>
        </header>

        <section className="space-y-3">
          <SectionHeader
            title="How we grade the answers"
            hint="Each answer is graded one or more ways. Here's what each grading method checks for."
          />
          <MethodsPanel
            scorers={scorers}
            hasFailures={failures.length > 0}
            hasFermi={scorers.includes("fermi_calibration")}
          />
        </section>

        <section className="space-y-3">
          <SectionHeader
            title="Worth a closer look"
            hint="A high average can still hide a handful of answers that were wrong — and sometimes confidently so. These are the answers that fell short, so you can read them yourself."
            details={`Flagged when an answer scores below a per-difficulty alarm bar (easy < ${fmt(thresholds.easy ?? 0.9)}, medium < ${fmt(thresholds.medium ?? 0.7)}); hard questions are excluded by design.`}
          />
          <FailuresPanel
            failures={failures}
            thresholds={thresholds}
            summary={failureSummary}
          />
        </section>

        {meta.track !== "factual" && (
          <section className="space-y-3">
            <SectionHeader
              title="Does the answer change with who's asking?"
              hint="The same question, asked by different kinds of people. A big gap means the model's answer depends on who's asking — for this kind of test, that's the headline result."
              details="Grouped by subdomain (e.g. voter_id); shows the spread between the highest- and lowest-scoring persona. Empty when a subdomain has only one persona."
            />
            <PersonaDeltaPanel rows={evalRows} />
          </section>
        )}

        <section className="space-y-3">
          <SectionHeader
            title="The questions"
            hint="Every question in this test, with its average score. Click a row to see the exact wording, the expected answer, and a real model response."
            details="Per-question scores are averaged across all runs for that question (any model, any persona)."
          />
          <TaskTable
            tasks={meta.tasks}
            byTask={byTask}
            scorers={scorers}
          />
        </section>

        <footer className="pt-8 border-t border-blue-200/60 dark:border-blue-400/15 text-sm text-zinc-500 dark:text-zinc-400">
          <p>
            Source:{" "}
            <a
              href={`https://github.com/justinshenk/civic-evals/tree/main/evals/${meta.name}`}
              className="text-blue-700 underline decoration-blue-300 underline-offset-4 dark:text-blue-300"
            >
              evals/{meta.name}/
            </a>
          </p>
        </footer>
      </div>
    </main>
  );
}

function TaskTable({
  tasks,
  byTask,
  scorers,
}: {
  tasks: TaskSummary[];
  byTask: Record<string, RollupRow[]>;
  scorers: string[];
}) {
  if (tasks.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        No tasks defined yet.
      </p>
    );
  }

  return (
    <div className="panel overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-blue-50/80 dark:bg-blue-500/10 text-left text-xs uppercase tracking-wide text-blue-900 dark:text-blue-200">
          <tr>
            <th className="px-3 py-2 font-medium">ID</th>
            <th className="px-3 py-2 font-medium">Question</th>
            <th className="px-3 py-2 font-medium">Difficulty</th>
            <th className="px-3 py-2 font-medium">Asker</th>
            <th className="px-3 py-2 font-medium">Expected</th>
            {scorers.map((s) => (
              <th key={s} className="px-3 py-2 font-medium font-mono text-[10px]">
                {s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {tasks.map((t) => (
            <TaskRow
              key={t.id}
              task={t}
              rows={byTask[t.id] ?? []}
              scorers={scorers}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TaskRow({
  task,
  rows,
  scorers,
}: {
  task: TaskSummary;
  rows: RollupRow[];
  scorers: string[];
}) {
  const byScorer = groupBy(rows, (r) => r.scorer);
  // Fermi tasks: find a row whose scorer surfaced truth/CI diagnostics so
  // the range bar has data to draw. Any provider's row works for shape.
  const fermiRow = rows.find(
    (r) => r.score_metadata && typeof r.score_metadata.truth === "number",
  );

  return (
    <>
      <tr className="bg-white dark:bg-zinc-950 align-top">
        <td className="px-3 py-3 font-mono text-xs whitespace-nowrap">
          <details className="group">
            <summary className="cursor-pointer hover:text-zinc-900 dark:hover:text-zinc-100">
              {task.id}
            </summary>
          </details>
        </td>
        <td className="px-3 py-3 text-zinc-700 dark:text-zinc-300 max-w-md">
          <span className="line-clamp-2">{task.input}</span>
        </td>
        <td className="px-3 py-3">
          <DifficultyBadge difficulty={task.difficulty} />
        </td>
        <td className="px-3 py-3 text-xs text-zinc-500 dark:text-zinc-400 font-mono">
          {task.persona || "—"}
        </td>
        <td className="px-3 py-3 text-xs">
          <RefusalBadge expected={task.refusal_expected} />
        </td>
        {scorers.map((s) => {
          const ss = byScorer[s] ?? [];
          const m = meanBy(ss, (r) => r.score);
          return (
            <td
              key={s}
              className="px-3 py-3 font-mono text-xs tabular-nums"
              title={ss[0]?.explanation || ""}
            >
              <ScoreCell score={m} />
            </td>
          );
        })}
      </tr>
      <tr className="bg-zinc-50/40 dark:bg-zinc-900/30">
        <td colSpan={5 + scorers.length} className="px-3 py-2">
          <details className="group text-xs">
            <summary className="cursor-pointer text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100">
              {task.scorer_kind === "rubric" ? "rubric" : "target"} ·{" "}
              <span className="font-mono">{task.subdomain}</span> ·{" "}
              <span className="font-mono">{task.tags.join(", ") || "—"}</span>
            </summary>
            <div className="pt-3 pb-1 space-y-3 text-zinc-600 dark:text-zinc-400 leading-relaxed">
              {fermiRow && fermiRow.score_metadata && (
                <FermiRangeBar diag={fermiRow.score_metadata} />
              )}
              {task.scorer_kind === "rubric" ? (
                <p>
                  <span className="text-zinc-400 dark:text-zinc-500 font-mono mr-2">rubric:</span>
                  {task.rubric_snippet || "(empty)"}
                </p>
              ) : (
                <p>
                  <span className="text-zinc-400 dark:text-zinc-500 font-mono mr-2">target:</span>
                  <span className="font-mono">{task.target ?? "(none)"}</span>
                </p>
              )}
              <p>
                <span className="text-zinc-400 dark:text-zinc-500 font-mono mr-2">source:</span>
                {task.source}
                <VerifiedBadge date={task.last_verified} />
              </p>
              <PersonaAttrsLine attrs={rows[0]?.persona_attrs ?? null} />
              {rows[0]?.completion && (
                <CompletionBlock
                  completion={rows[0].completion}
                  provider={rows[0].provider}
                />
              )}
              {rows[0]?.explanation && (
                <p>
                  <span className="text-zinc-400 dark:text-zinc-500 font-mono mr-2">last run:</span>
                  {rows[0].explanation}
                </p>
              )}
            </div>
          </details>
        </td>
      </tr>
    </>
  );
}

function DifficultyBadge({ difficulty }: { difficulty: "easy" | "medium" | "hard" }) {
  const colors = {
    easy: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400",
    medium: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-400",
    hard: "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-400",
  };
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-mono ${colors[difficulty]}`}
    >
      {difficulty}
    </span>
  );
}

function RefusalBadge({ expected }: { expected: "refuse" | "answer" | "hedge" | null }) {
  if (!expected) {
    return <span className="text-zinc-400 dark:text-zinc-600">—</span>;
  }
  const colors = {
    refuse: "border-rose-200 text-rose-600 dark:border-rose-900 dark:text-rose-400",
    answer: "border-emerald-200 text-emerald-700 dark:border-emerald-900 dark:text-emerald-400",
    hedge: "border-amber-200 text-amber-700 dark:border-amber-900 dark:text-amber-400",
  };
  return (
    <span
      className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-mono ${colors[expected]}`}
      title="The behavior the model should exhibit on this task"
    >
      {expected}
    </span>
  );
}

/**
 * Per-task ground-truth freshness indicator.
 *
 * Civic facts drift — election rules amend, statutes change, agency
 * URLs reorganize. ``last_verified`` is the date a maintainer last
 * checked the task's ground truth against its source. Three states:
 *
 * - **null** (unverified): renders an amber "unverified" pill so the
 *   reader knows the task hasn't been audited since import.
 * - **stale** (more than 12 months old): renders a rose "stale (date)"
 *   pill — the answer might be correct, but it deserves a fresh check.
 * - **fresh** (within 12 months): renders a quiet emerald "verified
 *   (date)" pill so the reader can trust the row.
 *
 * The threshold is 12 months because most civic-information drift
 * (annual deadline updates, post-election rule changes, biennial
 * statute reviews) cycles in that window.
 */
function VerifiedBadge({ date }: { date: string | null }) {
  if (!date) {
    return (
      <span
        className="ml-2 inline-flex items-center rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-mono text-amber-700 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-400"
        title="No last_verified date set on this task — ground truth hasn't been audited since import."
      >
        unverified
      </span>
    );
  }
  const verifiedAt = new Date(date);
  const ageDays = (Date.now() - verifiedAt.getTime()) / 86_400_000;
  const stale = ageDays > 365;
  const cls = stale
    ? "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-300"
    : "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-400";
  const label = stale ? "stale" : "verified";
  return (
    <span
      className={`ml-2 inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] font-mono ${cls}`}
      title={
        stale
          ? `Last verified ${date} — over 12 months old; deserves a fresh check.`
          : `Ground truth last verified ${date}.`
      }
    >
      {label} {date}
    </span>
  );
}

function ScoreCell({ score }: { score: number | null }) {
  if (score === null) return <span className="text-zinc-400">—</span>;
  let color = "text-zinc-600 dark:text-zinc-400";
  if (score >= 0.85) color = "text-emerald-600 dark:text-emerald-400";
  else if (score >= 0.6) color = "text-amber-600 dark:text-amber-400";
  else color = "text-rose-600 dark:text-rose-400";
  return <span className={color}>{fmt(score)}</span>;
}

function PersonaAttrsLine({
  attrs,
}: {
  attrs: RollupRow["persona_attrs"];
}) {
  if (!attrs) return null;
  // Skip default-y attrs to keep the line short; only show non-baseline values.
  const baseline: Record<string, string> = {
    lang_fluency: "fluent",
    education: "unspecified",
    political_lean: "unspecified",
    urgency: "medium",
    digital_literacy: "medium",
  };
  const interesting = Object.entries(attrs).filter(
    ([k, v]) => k !== "role" && baseline[k] !== v,
  );
  if (interesting.length === 0) return null;
  return (
    <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
      <span className="text-zinc-400 dark:text-zinc-500 font-mono mr-1">persona:</span>
      <span className="font-mono text-zinc-700 dark:text-zinc-200">{attrs.role}</span>
      {interesting.map(([k, v]) => (
        <span
          key={k}
          className="inline-flex items-center rounded bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-600 dark:text-zinc-300"
        >
          {k.replace(/_/g, " ")}={v}
        </span>
      ))}
    </p>
  );
}

function CompletionBlock({
  completion,
  provider,
}: {
  completion: string;
  provider: string;
}) {
  return (
    <div className="rounded border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-3">
      <div className="mb-1.5 flex items-center justify-between text-[10px] font-mono uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
        <span>model output</span>
        <span>{provider}</span>
      </div>
      <p className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-zinc-700 dark:text-zinc-300">
        {completion}
      </p>
    </div>
  );
}

function SectionHeader({
  title,
  hint,
  details,
}: {
  title: string;
  hint?: string;
  details?: React.ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <span aria-hidden className="ombre-rule mt-1 w-1 shrink-0 rounded-full" />
      <div className="space-y-2 max-w-3xl">
        <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">{title}</h2>
        {hint && (
          <p className="text-[15px] text-zinc-600 dark:text-zinc-300 leading-relaxed">{hint}</p>
        )}
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
    </div>
  );
}
