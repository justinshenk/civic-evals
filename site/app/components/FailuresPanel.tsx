"use client";

import { useMemo, useState } from "react";

// Import from the client-safe utils module rather than @/lib/rollup —
// the latter transitively imports node:fs (loadRollup reads the JSON
// file from disk) which Turbopack rejects from a "use client" component.
import { fmt, type FailureRow, type FailureSummaryRow } from "@/lib/rollup-utils";

/**
 * Surfaces individual completions whose score fell below the difficulty
 * threshold (easy < 0.9, medium < 0.7 by default — see analysis/rollup.py
 * `_FAILURE_THRESHOLDS`). Aggregate means hide the alarming-but-rare
 * cases; this panel makes them visible.
 *
 * Each failure carries a ``acknowledged_staleness`` verdict from an
 * LLM judge (Haiku by default): did the model hedge on training-data
 * freshness or point to an authoritative source? If yes, the failure
 * is "knew it didn't know" — concerning, but the right intervention
 * is web search, not retraining. If no, the model was confidently
 * wrong without epistemic caveat — that's the truly alarming bucket
 * and gets a red badge. ``staleness_kind`` distinguishes cutoff /
 * source / variation hedges; ``staleness_evidence`` is a short quote
 * the judge used to justify the verdict.
 *
 * Filter chips appear when there are more than 3 failures — below
 * that, a filter UI is more visual noise than help. Filters are
 * client-side only (the panel is a "use client" component); they
 * don't change the rollup or the URL, so the page is still SSG.
 *
 * Empty state is intentional and reassuring — "nothing to see here" is
 * a meaningful signal, not a layout bug.
 */
export function FailuresPanel({
  failures,
  thresholds,
  summary,
}: {
  failures: FailureRow[];
  thresholds: Record<string, number>;
  summary: FailureSummaryRow | undefined;
}) {
  const [provider, setProvider] = useState<string>("all");
  const [hedge, setHedge] = useState<"all" | "hedged" | "no-hedge">("all");
  const [scorer, setScorer] = useState<string>("all");

  const providers = useMemo(
    () => Array.from(new Set(failures.map((f) => f.provider))).sort(),
    [failures],
  );
  const scorers = useMemo(
    () => Array.from(new Set(failures.map((f) => f.scorer))).sort(),
    [failures],
  );

  const filtered = useMemo(
    () =>
      failures.filter((f) => {
        if (provider !== "all" && f.provider !== provider) return false;
        if (scorer !== "all" && f.scorer !== scorer) return false;
        if (hedge === "hedged" && !f.acknowledged_staleness) return false;
        if (hedge === "no-hedge" && f.acknowledged_staleness !== false) {
          // false (judged, no hedge) is the "no-hedge" bucket; null
          // (not judged) is excluded from both buckets.
          return false;
        }
        return true;
      }),
    [failures, provider, hedge, scorer],
  );

  if (failures.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 p-4 text-sm text-zinc-500 dark:text-zinc-400">
        No completions on this eval scored below the alarm threshold
        (easy &lt; {fmt(thresholds.easy ?? 0.9)}, medium &lt;{" "}
        {fmt(thresholds.medium ?? 0.7)}).
      </div>
    );
  }

  // 3 was picked by feel: with ≤3 cards, scrolling is faster than
  // reading filter chips. Above that, filters earn their pixels.
  const showFilters = failures.length > 3;

  return (
    <div className="space-y-3">
      {summary && summary.n_failures > 0 && (
        <StalenessSummary summary={summary} />
      )}
      {showFilters && (
        <FailureFilters
          providers={providers}
          scorers={scorers}
          provider={provider}
          setProvider={setProvider}
          hedge={hedge}
          setHedge={setHedge}
          scorer={scorer}
          setScorer={setScorer}
          total={failures.length}
          shown={filtered.length}
        />
      )}
      {filtered.length === 0 ? (
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/40 p-4 text-sm text-zinc-600 dark:text-zinc-400">
          No failures match the current filter. Clear it to see all{" "}
          {failures.length}.
        </div>
      ) : (
        filtered.map((f, i) => (
          <FailureCard key={`${f.task_id}-${f.provider}-${f.scorer}-${i}`} f={f} />
        ))
      )}
    </div>
  );
}

/**
 * Three small segmented controls. Each shows current selection and
 * clicking a chip toggles that filter back to "all" — there's no
 * separate clear button because the controls are themselves the clear
 * affordance.
 */
function FailureFilters({
  providers,
  scorers,
  provider,
  setProvider,
  hedge,
  setHedge,
  scorer,
  setScorer,
  total,
  shown,
}: {
  providers: string[];
  scorers: string[];
  provider: string;
  setProvider: (v: string) => void;
  hedge: "all" | "hedged" | "no-hedge";
  setHedge: (v: "all" | "hedged" | "no-hedge") => void;
  scorer: string;
  setScorer: (v: string) => void;
  total: number;
  shown: number;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-3 py-2 text-xs">
      <span className="text-zinc-500 dark:text-zinc-400">
        Showing <strong className="text-zinc-900 dark:text-zinc-100">{shown}</strong> of {total}
      </span>
      {providers.length > 1 && (
        <FilterGroup
          label="provider"
          value={provider}
          onChange={setProvider}
          options={["all", ...providers]}
        />
      )}
      <FilterGroup
        label="hedge"
        value={hedge}
        onChange={(v) => setHedge(v as "all" | "hedged" | "no-hedge")}
        options={["all", "hedged", "no-hedge"]}
      />
      {scorers.length > 1 && (
        <FilterGroup
          label="scorer"
          value={scorer}
          onChange={setScorer}
          options={["all", ...scorers]}
        />
      )}
    </div>
  );
}

function FilterGroup({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="font-mono uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
        {label}:
      </span>
      <span className="inline-flex flex-wrap gap-1">
        {options.map((opt) => {
          const active = opt === value;
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onChange(opt)}
              className={
                active
                  ? "rounded border border-zinc-400 bg-zinc-100 px-1.5 py-0.5 font-mono text-[10px] text-zinc-900 dark:border-zinc-500 dark:bg-zinc-800 dark:text-zinc-100"
                  : "rounded border border-zinc-200 bg-white px-1.5 py-0.5 font-mono text-[10px] text-zinc-500 hover:border-zinc-400 hover:text-zinc-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400 dark:hover:border-zinc-600 dark:hover:text-zinc-200"
              }
            >
              {opt}
            </button>
          );
        })}
      </span>
    </span>
  );
}

function StalenessSummary({ summary }: { summary: FailureSummaryRow }) {
  const rate = summary.ack_rate ?? 0;
  const allHedged = summary.n_acknowledged === summary.n_failures;
  const noneHedged = summary.n_acknowledged === 0;
  const tone = allHedged
    ? "border-amber-200 bg-amber-50/60 text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200"
    : noneHedged
      ? "border-rose-200 bg-rose-50/60 text-rose-900 dark:border-rose-900/40 dark:bg-rose-950/30 dark:text-rose-200"
      : "border-zinc-200 bg-zinc-50 text-zinc-700 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-300";
  return (
    <div className={`rounded-lg border ${tone} px-4 py-3 text-sm leading-relaxed`}>
      <strong>
        {summary.n_acknowledged}/{summary.n_failures} ({(rate * 100).toFixed(0)}%)
      </strong>{" "}
      of failures came with a staleness or jurisdiction hedge — the model
      acknowledged its training data may be out of date, or pointed the
      asker at a Secretary of State / EAC / state-office source.{" "}
      {summary.n_unacknowledged > 0 && (
        <span>
          The remaining{" "}
          <strong>{summary.n_unacknowledged}</strong> were confidently wrong
          with no epistemic caveat — those are the cards to inspect first.
        </span>
      )}
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
        {f.refused && <RefusalBadge />}
        <HedgeBadge
          acknowledged={f.acknowledged_staleness}
          kind={f.staleness_kind}
          evidence={f.staleness_evidence}
        />
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

function HedgeBadge({
  acknowledged,
  kind,
  evidence,
}: {
  acknowledged: boolean | null;
  kind: string | null;
  evidence: string | null;
}) {
  if (acknowledged === null) return null; // not judged (search eval, missing key, judge crash)
  if (acknowledged) {
    const label = kind && kind !== "none" ? kind : "hedged";
    const title = evidence ? `evidence: "${evidence}"` : "";
    return (
      <span
        className="inline-flex items-center rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[10px] font-mono text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-400"
        title={title}
      >
        {label}
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center rounded border border-rose-300 bg-rose-100 px-1.5 py-0.5 text-[10px] font-mono text-rose-700 dark:border-rose-800 dark:bg-rose-950/60 dark:text-rose-300"
      title="No staleness or authoritative-source hedge detected — confidently wrong."
    >
      no hedge
    </span>
  );
}

/**
 * Marks a failure whose score is a refusal credit (0.5 in fermi) rather
 * than a real numeric measurement. The model declined to commit to a
 * number — either by writing prose or by emitting a zero point with
 * zero-width interval against a non-zero truth. Distinct from the
 * staleness hedge: the refusal label is about the *score*, the hedge
 * label is about *why* the model refused.
 */
function RefusalBadge() {
  return (
    <span
      className="inline-flex items-center rounded border border-amber-300 bg-amber-50 px-1.5 py-0.5 text-[10px] font-mono text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/40 dark:text-amber-300"
      title="Model declined to commit to a number; scored 0.5 (refusal credit) rather than as a confident wrong answer."
    >
      refusal-shaped
    </span>
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
