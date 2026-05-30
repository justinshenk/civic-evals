import { fmt, type BiasFit, type Rollup } from "@/lib/rollup";

/**
 * Surfaces the cross-model substantive-policy bias measurement
 * (analysis/multi_model_bias.py) on the home page.
 *
 * Reader question: "do these models rate identical candidates
 * differently when only the policy direction changes?" That's harder
 * to answer from the per-eval pages — bias is *cross-model*, not
 * within-eval, and it's measured by an OLS over a synthetic factorial
 * rather than by a per-task scorer. This panel lifts the headline
 * finding (years-of-experience equivalent) out of the analysis script
 * onto the public surface, with the methodology link.
 *
 * Sign convention: positive years_per_package = D-typical platform
 * rated higher than R-typical (controlling for label, experience,
 * rigor). The bar's length is |yrs|; the chart caption names what
 * positive means so readers don't have to chase the docstring.
 *
 * Renders nothing when ``rollup.bias`` is missing — keeps the home
 * page clean on environments that haven't run the OpenRouter
 * factorial yet.
 */
export function BiasPanel({ rollup }: { rollup: Rollup }) {
  const bias = rollup.bias;
  if (!bias || bias.length === 0) return null;

  // Pre-sorted by |yrs| desc on the analysis side; defensive re-sort
  // anyway so the panel survives malformed rollups.
  const rows = [...bias].sort(
    (a, b) => Math.abs(b.years_per_package ?? 0) - Math.abs(a.years_per_package ?? 0),
  );

  const maxAbs = Math.max(
    ...rows.map((r) => Math.abs(r.years_per_package ?? 0)),
    1, // floor so a tiny effect doesn't blow the bar to 100% width
  );

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden">
        <div className="px-4 py-3 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900/40">
          <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            <strong>Positive bar = D-typical platform rated higher</strong> (the
            R-typical-platform candidate is rated like they have this many{" "}
            <em>fewer</em> years of equivalent experience). Bar length = |years|;
            color encodes statistical significance.
          </p>
        </div>
        <div className="divide-y divide-zinc-200 dark:divide-zinc-800">
          {rows.map((r) => (
            <BiasRow key={r.model} fit={r} maxAbs={maxAbs} />
          ))}
        </div>
      </div>
      <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed max-w-3xl">
        Method: synthetic 24-cell factorial (party × policy_package ×
        experience × rigor) for an open school-board seat. 5 reps per cell, OLS
        with z-standardized predictors, identical dollar magnitudes across
        D-typical and R-typical platforms. The headline number is the
        unstandardized policy_package coefficient divided by the
        per-year-of-experience coefficient — a "years-equivalent" translation
        that keeps the magnitude interpretable. Source:{" "}
        <a
          href="https://github.com/justinshenk/civic-evals/blob/main/analysis/multi_model_bias.py"
          className="underline decoration-zinc-400 underline-offset-4 hover:text-zinc-900 dark:hover:text-zinc-100"
        >
          analysis/multi_model_bias.py
        </a>
        ; full write-up:{" "}
        <a
          href="https://github.com/justinshenk/civic-evals/blob/main/analysis/multi_model_results.md"
          className="underline decoration-zinc-400 underline-offset-4 hover:text-zinc-900 dark:hover:text-zinc-100"
        >
          analysis/multi_model_results.md
        </a>
        .
      </p>
    </div>
  );
}

function BiasRow({ fit, maxAbs }: { fit: BiasFit; maxAbs: number }) {
  const yrs = fit.years_per_package;
  const pct =
    yrs === null ? 0 : Math.min(100, (Math.abs(yrs) / maxAbs) * 100);
  const significant = (fit.p_package ?? 1) < 0.001;
  const color = significant
    ? "bg-rose-500 dark:bg-rose-600"
    : "bg-zinc-300 dark:bg-zinc-700";

  return (
    <div className="grid grid-cols-12 gap-3 items-center px-4 py-2.5 text-sm">
      <code className="col-span-4 font-mono text-xs text-zinc-700 dark:text-zinc-300 break-all">
        {fit.model}
      </code>
      <div className="col-span-6 relative h-5 rounded bg-zinc-100 dark:bg-zinc-900 overflow-hidden">
        <div
          className={`absolute left-0 top-0 bottom-0 ${color} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="col-span-2 text-right tabular-nums">
        <span className={significant ? "font-semibold" : "text-zinc-500 dark:text-zinc-400"}>
          {yrs === null ? "—" : `+${fmt(yrs, 1)} yr`}
        </span>
        <span className="ml-1 text-[10px] text-zinc-500 dark:text-zinc-400">
          {fit.p_package !== null && fit.p_package < 1e-3
            ? "p<10⁻³"
            : `p=${fmt(fit.p_package, 2)}`}
        </span>
      </div>
    </div>
  );
}
