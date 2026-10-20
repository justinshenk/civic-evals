import { FINDINGS_SOURCE_ROOT, PERSONA_FINDINGS } from "@/lib/personaFindings";

const linkClass = "text-blue-700 underline decoration-blue-300 underline-offset-4 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-200";

export function PersonaFindingsPanel() {
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Claude Haiku 4.5 · May 2026 · 45 answers per persona per condition · Claude Sonnet 4.5 judge
      </p>
      <div className="grid gap-4 md:grid-cols-3">
        {PERSONA_FINDINGS.map((finding) => (
          <article key={finding.title} className="card flex flex-col gap-3 p-5">
            <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{finding.title}</h3>
            <p className="ombre-text text-3xl font-semibold tabular-nums">{finding.value}</p>
            <p className="text-sm font-medium tabular-nums">{finding.detail}</p>
            <p className="flex-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">{finding.summary}</p>
            <a className={`${linkClass} text-sm`} href={`${FINDINGS_SOURCE_ROOT}${finding.source}`}>
              Read the source report →
            </a>
          </article>
        ))}
      </div>
      <p className="max-w-3xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
        Lean is measured on a −10 to +10 scale. These findings cover one subject model and two
        topics. They do not establish the behavior of today&rsquo;s models. The reports give the
        immigration baseline as 9.54 and 9.53; each figure above preserves its source report.
      </p>
      <p className="max-w-3xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
        A separate candidate-rating experiment found an average <strong>~67%</strong> reduction
        in the user-persona gap on Sonnet across three selected high-gap cells. That is a different
        experiment and rating scale.{" "}
        <a className={linkClass} href={`${FINDINGS_SOURCE_ROOT}persona_l0_mitigation_results.md`}>
          Read the candidate-rating mitigation report →
        </a>
      </p>
    </div>
  );
}
