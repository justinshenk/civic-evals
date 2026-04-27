import { fmt, type CalibrationStat, type Rollup } from "@/lib/rollup";

/**
 * Calibration AUROC panel.
 *
 * For fermi-scored evals: did the model give narrower CIs on the
 * questions it got right? AUROC of (1 / CI-width) vs (point estimate
 * within ±10% of truth). 0.5 = chance, 1.0 = perfect.
 *
 * The metric mirrors the calibration AUROC reported by Vashurin et al.
 * (TACL 2025), specialized to interval forecasts since the eval already
 * extracts a stated CI.
 */
export function CalibrationPanel({ rollup }: { rollup: Rollup }) {
  const stats = rollup.calibration_stats ?? [];

  if (stats.length === 0) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        No calibration data yet — needs fermi-scored runs.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-sm">
        <thead className="bg-zinc-50 dark:bg-zinc-900/50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
          <tr>
            <th className="px-3 py-2 font-medium">Eval</th>
            <th className="px-3 py-2 font-medium">Provider</th>
            <th className="px-3 py-2 font-medium text-right">AUROC</th>
            <th className="px-3 py-2 font-medium text-right">n</th>
            <th className="px-3 py-2 font-medium text-right">accurate</th>
            <th className="px-3 py-2 font-medium">reading</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800 bg-white dark:bg-zinc-950">
          {stats.map((s, i) => (
            <CalibRow key={`${s.eval}:${s.provider}:${i}`} stat={s} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CalibRow({ stat }: { stat: CalibrationStat }) {
  const reading = readAUROC(stat.value, stat.n_correct, stat.n);
  return (
    <tr>
      <td className="px-3 py-2 font-mono text-xs">{stat.eval}</td>
      <td className="px-3 py-2 font-mono text-[11px] text-zinc-500 dark:text-zinc-400">
        {stat.provider}
      </td>
      <td className="px-3 py-2 text-right font-mono tabular-nums">
        <AUROCCell value={stat.value} />
      </td>
      <td className="px-3 py-2 text-right font-mono text-xs text-zinc-500 dark:text-zinc-400 tabular-nums">
        {stat.n}
      </td>
      <td className="px-3 py-2 text-right font-mono text-xs text-zinc-500 dark:text-zinc-400 tabular-nums">
        {stat.n_correct}/{stat.n}
      </td>
      <td className="px-3 py-2 text-xs text-zinc-600 dark:text-zinc-400">{reading}</td>
    </tr>
  );
}

function AUROCCell({ value }: { value: number | null }) {
  if (value === null) return <span className="text-zinc-400">—</span>;
  let color = "text-zinc-600 dark:text-zinc-400";
  if (value >= 0.75) color = "text-emerald-600 dark:text-emerald-400";
  else if (value >= 0.6) color = "text-amber-600 dark:text-amber-400";
  else if (value < 0.5) color = "text-rose-600 dark:text-rose-400";
  return <span className={color}>{fmt(value, 3)}</span>;
}

function readAUROC(v: number | null, nCorrect: number, n: number): string {
  if (v === null) {
    if (nCorrect === n) return "all correct — AUROC undefined";
    if (nCorrect === 0) return "all wrong — AUROC undefined";
    return "insufficient data";
  }
  if (v >= 0.75) return "well-ranked: narrower CI predicts being right";
  if (v >= 0.6) return "modestly calibrated";
  if (v >= 0.5) return "barely above chance";
  return "anti-calibrated: narrower CI predicts being wrong";
}
