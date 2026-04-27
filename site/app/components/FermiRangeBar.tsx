import type { ScoreDiagnostics } from "@/lib/rollup";

/**
 * Horizontal range visualization for Fermi calibration tasks.
 *
 * Shows the model's 80% CI as a band, the point estimate as a dot, and
 * the truth as a vertical marker. The x-axis is normalized to span
 * [min(truth, ci_low, est) − pad, max(truth, ci_high, est) + pad] so
 * shapes are comparable across questions of wildly different magnitudes.
 *
 * Color encodes calibration: green if truth lies in CI, rose otherwise.
 */
export function FermiRangeBar({ diag }: { diag: ScoreDiagnostics }) {
  const { truth, estimate, ci_low, ci_high } = diag;
  if (
    typeof truth !== "number" ||
    typeof estimate !== "number" ||
    typeof ci_low !== "number" ||
    typeof ci_high !== "number"
  ) {
    return null;
  }

  const lo = Math.min(truth, estimate, ci_low);
  const hi = Math.max(truth, estimate, ci_high);
  const span = hi - lo || Math.max(Math.abs(truth), 1);
  const pad = span * 0.15;
  const xMin = lo - pad;
  const xMax = hi + pad;
  const range = xMax - xMin || 1;
  const pct = (v: number) => ((v - xMin) / range) * 100;

  const contains = ci_low <= truth && truth <= ci_high;
  const bandColor = contains
    ? "bg-emerald-200/70 dark:bg-emerald-900/50 border-emerald-400 dark:border-emerald-700"
    : "bg-rose-200/70 dark:bg-rose-900/50 border-rose-400 dark:border-rose-700";
  const estDot = contains
    ? "bg-emerald-600 dark:bg-emerald-400"
    : "bg-rose-600 dark:bg-rose-400";

  // Width is at least 2px so a degenerate-tight CI is still visible.
  const ciStart = pct(ci_low);
  const ciWidth = Math.max(pct(ci_high) - ciStart, 0.5);

  return (
    <div className="space-y-1.5">
      <div className="relative h-6">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-zinc-200 dark:bg-zinc-700" />
        <div
          className={`absolute top-1/2 h-3 -translate-y-1/2 rounded-sm border ${bandColor}`}
          style={{ left: `${ciStart}%`, width: `${ciWidth}%` }}
          title={`CI80 [${fmtNum(ci_low)}, ${fmtNum(ci_high)}]`}
        />
        <div
          className="absolute top-0 bottom-0 w-px bg-zinc-900 dark:bg-zinc-100"
          style={{ left: `${pct(truth)}%` }}
          title={`truth ${fmtNum(truth)}`}
        />
        <div
          className={`absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full ${estDot}`}
          style={{ left: `${pct(estimate)}%` }}
          title={`estimate ${fmtNum(estimate)}`}
        />
      </div>
      <div className="flex justify-between text-[10px] font-mono tabular-nums text-zinc-500 dark:text-zinc-400">
        <span>{fmtNum(xMin)}</span>
        <span className="space-x-3">
          <span>est <span className="text-zinc-700 dark:text-zinc-200">{fmtNum(estimate)}</span></span>
          <span>truth <span className="text-zinc-700 dark:text-zinc-200">{fmtNum(truth)}</span></span>
          <span>
            CI{" "}
            <span className="text-zinc-700 dark:text-zinc-200">
              [{fmtNum(ci_low)}, {fmtNum(ci_high)}]
            </span>
          </span>
        </span>
        <span>{fmtNum(xMax)}</span>
      </div>
    </div>
  );
}

function fmtNum(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${(v / 1e6).toFixed(2)}M`;
  if (abs >= 1e4) return `${(v / 1e3).toFixed(1)}k`;
  if (Number.isInteger(v)) return v.toLocaleString();
  return v.toFixed(2);
}
