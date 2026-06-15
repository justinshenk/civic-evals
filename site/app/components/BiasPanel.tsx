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
      <div className="panel">
        <div className="px-4 py-3 border-b border-blue-200/60 dark:border-blue-400/15 bg-blue-50/70 dark:bg-blue-500/10">
          <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
            A <strong>longer bar means a bigger tilt</strong> toward the Democratic-leaning
            platform. The number reads as &ldquo;years of extra experience&rdquo; the
            Republican-leaning candidate would need to close the gap. A solid blue bar means the
            tilt is statistically clear; a faint grey bar means it&rsquo;s within the noise.
          </p>
        </div>
        <div className="divide-y divide-blue-100 dark:divide-blue-400/10">
          {rows.map((r) => (
            <BiasRow key={r.model} fit={r} maxAbs={maxAbs} />
          ))}
        </div>
      </div>
      <details className="group max-w-3xl">
        <summary className="inline-flex w-fit cursor-pointer items-center gap-1.5 rounded-full border border-blue-200/70 bg-blue-50/60 px-2.5 py-1 text-xs font-medium text-blue-700 list-none [&::-webkit-details-marker]:hidden hover:bg-blue-100/70 dark:border-blue-400/20 dark:bg-blue-500/10 dark:text-blue-300 dark:hover:bg-blue-500/20">
          <span aria-hidden className="transition-transform group-open:rotate-90">
            ▸
          </span>
          Technical details
        </summary>
        <p className="mt-2 rounded-lg border border-blue-200/50 bg-blue-50/30 px-3 py-2.5 text-xs leading-relaxed text-zinc-600 dark:border-blue-400/15 dark:bg-blue-500/5 dark:text-zinc-400">
          Synthetic 24-cell factorial (party × policy_package × experience × rigor) for an open
          school-board seat. 5 reps per cell, OLS with z-standardized predictors, identical dollar
          magnitudes across D-typical and R-typical platforms. The headline number is the
          unstandardized policy_package coefficient divided by the per-year-of-experience
          coefficient — a &ldquo;years-equivalent&rdquo; translation that keeps the magnitude
          interpretable. Source:{" "}
          <a
            href="https://github.com/justinshenk/civic-evals/blob/main/analysis/multi_model_bias.py"
            className="text-blue-700 underline decoration-blue-300 underline-offset-4 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-200"
          >
            analysis/multi_model_bias.py
          </a>
          ; full write-up:{" "}
          <a
            href="https://github.com/justinshenk/civic-evals/blob/main/analysis/multi_model_results.md"
            className="text-blue-700 underline decoration-blue-300 underline-offset-4 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-200"
          >
            analysis/multi_model_results.md
          </a>
          .
        </p>
      </details>
    </div>
  );
}

function BiasRow({ fit, maxAbs }: { fit: BiasFit; maxAbs: number }) {
  const yrs = fit.years_per_package;
  const pct =
    yrs === null ? 0 : Math.min(100, (Math.abs(yrs) / maxAbs) * 100);
  const significant = (fit.p_package ?? 1) < 0.001;
  const color = significant
    ? "ombre-fill-h"
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
