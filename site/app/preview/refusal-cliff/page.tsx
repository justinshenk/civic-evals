import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Refusal cliff — preview",
  description: "Internal preview of the openendedness_ladder v2 finding.",
  robots: {
    index: false,
    follow: false,
    googleBot: { index: false, follow: false },
    nocache: true,
  },
};

export default function RefusalCliffPreview() {
  return (
    <main className="flex-1 w-full">
      <div className="mx-auto max-w-4xl px-6 py-12 space-y-10">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-widest text-amber-700 dark:text-amber-400">
            Internal preview · not indexed · pre-publication
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">The refusal cliff</h1>
          <p className="max-w-3xl text-zinc-600 dark:text-zinc-400 leading-relaxed">
            Both Claude Haiku 4.5 and GPT-4o flip from ~0% refusal to ≥86% refusal at the
            same boundary — between rung 2 (factual) and rung 3 (interpretive) of the
            openendedness ladder. The flip-point is identical across the two flagship
            models, suggesting it is a property of the modern RLHF safety-training
            distribution rather than a per-model quirk.
          </p>
        </header>

        <figure className="space-y-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/preview/refusal-cliff.png"
            alt="Three-panel figure: refusal rate, frame entropy, and stance σ across openendedness rungs r1–r5 for Claude Haiku 4.5 and GPT-4o."
            className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800"
          />
          <figcaption className="text-sm text-zinc-500 dark:text-zinc-400">
            <code className="font-mono">openendedness_ladder</code> v2 · n = 25 prompts × 10
            epochs × 2 models · May 2026
          </figcaption>
        </figure>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Refusal rate by rung</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-200 dark:border-zinc-800 text-left">
                <th className="py-2 font-medium">Model</th>
                <th className="py-2 font-medium text-right">r1 fact</th>
                <th className="py-2 font-medium text-right">r2 fact</th>
                <th className="py-2 font-medium text-right">r3 interp</th>
                <th className="py-2 font-medium text-right">r4 interp</th>
                <th className="py-2 font-medium text-right">r5 interp</th>
              </tr>
            </thead>
            <tbody className="font-mono">
              <tr className="border-b border-zinc-100 dark:border-zinc-900">
                <td className="py-2">claude-haiku-4-5</td>
                <td className="py-2 text-right">0%</td>
                <td className="py-2 text-right">0%</td>
                <td className="py-2 text-right font-semibold text-red-700 dark:text-red-400">
                  100%
                </td>
                <td className="py-2 text-right">92%</td>
                <td className="py-2 text-right">98%</td>
              </tr>
              <tr>
                <td className="py-2">gpt-4o-2024-08-06</td>
                <td className="py-2 text-right">0%</td>
                <td className="py-2 text-right">6%</td>
                <td className="py-2 text-right font-semibold text-red-700 dark:text-red-400">
                  94%
                </td>
                <td className="py-2 text-right">86%</td>
                <td className="py-2 text-right">94%</td>
              </tr>
            </tbody>
          </table>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            r1–r2 are factual (definite answers); r3–r5 are interpretive (multiple
            defensible readings). Same five topics: voter ID, universal mail-in voting,
            ranked-choice voting, independent redistricting, individual contribution
            limits.
          </p>
        </section>

        <section className="space-y-3 text-sm text-zinc-700 dark:text-zinc-300">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Why this matters
          </h2>
          <p>
            On factual civic questions the model engages; on interpretive ones it nearly
            always hedges with refusal-shaped framings (&ldquo;the evidence is genuinely mixed&rdquo;,
            &ldquo;this is contested&rdquo;, &ldquo;valid views on multiple sides&rdquo;). The transition is sharp
            and structural, not gradient. A user who needs substantive interpretive
            engagement on civic policy is pushed elsewhere — that is itself a failure mode
            of LLMs as a civic-information channel.
          </p>
          <p>
            Frame entropy peaks at r4 (~0.85 bits) and drops at r5 as refusal-shaped
            framings dominate — Shannon H is highest where models still occasionally
            split between e.g. <code className="font-mono">turnout</code> and{" "}
            <code className="font-mono">equity</code> framings even within the refusal
            envelope.
          </p>
        </section>

        <section className="space-y-2 text-sm text-zinc-600 dark:text-zinc-400">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Status &amp; provenance
          </h2>
          <ul className="list-disc list-inside space-y-1">
            <li>
              Eval: <code className="font-mono">evals/openendedness_ladder/</code> (v2)
            </li>
            <li>
              Figure source:{" "}
              <code className="font-mono">evals/openendedness_ladder/figure.png</code>
            </li>
            <li>
              Generator:{" "}
              <code className="font-mono">analysis/openendedness_figure.py</code>
            </li>
            <li>
              Run dates: 2026-05-09 (two log artifacts in <code className="font-mono">logs/</code>)
            </li>
            <li>Judge: different-provider per response (see <code className="font-mono">p3.providers.pick_judge</code>)</li>
          </ul>
        </section>

        <footer className="pt-8 border-t border-zinc-200 dark:border-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
          This page is intentionally unlinked from the public site and excluded from
          robots. Share the URL with collaborators only.
        </footer>
      </div>
    </main>
  );
}
