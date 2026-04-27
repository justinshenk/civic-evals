import { notFound } from "next/navigation";
import Link from "next/link";
import { FermiRangeBar } from "@/app/components/FermiRangeBar";
import {
  fmt,
  groupBy,
  loadRollup,
  meanBy,
  type RollupRow,
  type TaskSummary,
} from "@/lib/rollup";

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

  return (
    <main className="flex-1 w-full">
      <div className="mx-auto max-w-6xl px-6 py-12 space-y-10">
        <nav className="text-sm">
          <Link
            href="/"
            className="text-zinc-500 dark:text-zinc-400 hover:text-zinc-900 dark:hover:text-zinc-100 underline decoration-zinc-300 dark:decoration-zinc-700 underline-offset-3"
          >
            ← all evals
          </Link>
        </nav>

        <header className="space-y-3">
          <p className="text-xs uppercase tracking-widest text-zinc-500 dark:text-zinc-400">
            CORDA · P3 · eval
          </p>
          <h1 className="font-mono text-3xl font-semibold tracking-tight">{meta.name}</h1>
          <p className="max-w-3xl text-zinc-600 dark:text-zinc-400 leading-relaxed">
            {meta.description || "No description provided."}
          </p>
          <div className="flex flex-wrap gap-6 pt-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">{meta.task_count}</strong> tasks
            </span>
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">{scorers.length}</strong>{" "}
              scorers ({scorers.join(", ") || "—"})
            </span>
            <span>
              overall mean{" "}
              <strong className="text-zinc-900 dark:text-zinc-100">{fmt(overall)}</strong>
            </span>
            <a
              href={meta.readme_url}
              className="underline decoration-zinc-400 underline-offset-4 hover:text-zinc-900 dark:hover:text-zinc-100"
            >
              README →
            </a>
          </div>
        </header>

        <section className="space-y-3">
          <SectionHeader
            title="Tasks"
            hint="Each row is one task. Per-task scores are averaged across all rollup rows for that task (any provider, any persona). Click a task ID to expand its full rubric or target."
          />
          <TaskTable
            tasks={meta.tasks}
            byTask={byTask}
            scorers={scorers}
          />
        </section>

        <footer className="pt-8 border-t border-zinc-200 dark:border-zinc-800 text-sm text-zinc-500 dark:text-zinc-400">
          <p>
            Source:{" "}
            <a
              href={`https://github.com/justinshenk/civic-evals/tree/main/evals/${meta.name}`}
              className="underline decoration-zinc-400 underline-offset-4"
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
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-sm">
        <thead className="bg-zinc-50 dark:bg-zinc-900/50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          <tr>
            <th className="px-3 py-2 font-medium">Task</th>
            <th className="px-3 py-2 font-medium">Question</th>
            <th className="px-3 py-2 font-medium">Difficulty</th>
            <th className="px-3 py-2 font-medium">Persona</th>
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

function SectionHeader({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="space-y-1">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-3xl">{hint}</p>
    </div>
  );
}
