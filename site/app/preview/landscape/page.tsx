import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Landscape — preview",
  description: "Internal preview of the civic-LLM evaluation landscape map.",
  robots: {
    index: false,
    follow: false,
    googleBot: { index: false, follow: false },
    nocache: true,
  },
};

export default function LandscapePreview() {
  return (
    <main className="flex-1 w-full">
      <div className="mx-auto max-w-5xl px-6 py-12 space-y-10">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-widest text-amber-700 dark:text-amber-400">
            Internal preview · not indexed · pre-publication
          </p>
          <h1 className="text-3xl font-semibold tracking-tight">
            The civic-LLM evaluation landscape
          </h1>
          <p className="max-w-3xl text-zinc-600 dark:text-zinc-400 leading-relaxed">
            A map of where the work in this paper sits relative to existing actors.
            Rows = research topics in civic-LLM evaluation; columns = groups working
            in the space. Yellow halos mark the three rows where CORDA P3&rsquo;s proposed
            paper is the only &ldquo;owns it&rdquo; claim — the white space being claimed.
          </p>
        </header>

        <figure className="space-y-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/preview/landscape.png"
            alt="Matrix figure: 11 research topics by 9 research groups. Filled green cells mark strong claims; light grey circles mark adjacent or partial work. Three rows (refusal as object, persona × pressure, cross-axis failure concentration) are highlighted as CORDA P3's novel territory."
            className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white"
          />
          <figcaption className="text-sm text-zinc-500 dark:text-zinc-400">
            Generator:{" "}
            <code className="font-mono">analysis/landscape_figure.py</code> · edit the
            TOPICS / GROUPS / MATRIX constants when the literature shifts.
          </figcaption>
        </figure>

        <section className="space-y-4 text-sm text-zinc-700 dark:text-zinc-300">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            How to read it
          </h2>
          <ul className="list-disc list-outside ml-5 space-y-2">
            <li>
              <strong>●</strong> filled green = group owns this topic / has a strong
              published claim there.
            </li>
            <li>
              <strong>○</strong> light grey = adjacent or partial — the group has done
              related work but doesn&rsquo;t headline this topic.
            </li>
            <li>
              <strong>blank</strong> = the group hasn&rsquo;t worked here.
            </li>
            <li>
              <strong>★ + yellow halo</strong> = rows where CORDA P3&rsquo;s proposed paper
              is the only owns-it claim. These are the three claims the paper rests on
              being genuinely novel.
            </li>
            <li>
              The dashed vertical line separates existing literature from CORDA P3&rsquo;s
              two columns: <em>current repo</em> (Findings 1 + 2 already produced) and{" "}
              <em>this paper §§1–6</em> (what the proposed paper claims).
            </li>
          </ul>
        </section>

        <section className="space-y-3 text-sm text-zinc-700 dark:text-zinc-300">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            The three novel rows (the headline argument)
          </h2>
          <ol className="list-decimal list-outside ml-5 space-y-2">
            <li>
              <strong>Refusal / abstention as object of study.</strong> Most existing
              work treats refusal as a carve-out from aggregation, not as itself a
              behavior to characterize. P6 / Maxi are adjacent (they treat N/A as a
              carve-out too, but flagged that refusal-as-signal is on their v2
              roadmap). The refusal cliff finding is the cleanest unclaimed result.
            </li>
            <li>
              <strong>Persona × pressure interaction.</strong> Persona-conditioning
              and multi-turn sycophancy are each studied in isolation; the
              cross-effect — does persona conditioning amplify or dampen pressure
              effects, or vice versa — is not under any single paper yet.
            </li>
            <li>
              <strong>Cross-axis failure concentration.</strong> The synthesis move:
              given the failures we measure across providers, personas, pressure
              types, and refusal-vs-substance, where do they concentrate? This is
              §6 of the paper and is what makes the paper&rsquo;s framing distinct from
              CAIS (single axis), P6 / Maxi (single rubric), and existing factuality
              benchmarks (single eval).
            </li>
          </ol>
        </section>

        <section className="space-y-3 text-sm text-zinc-700 dark:text-zinc-300">
          <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            What this map says about positioning
          </h2>
          <p>
            <strong>Finding 2 (substantive-policy bias) is no longer a headline.</strong>{" "}
            CAIS (Phan + al., 2026) and earlier audit work (Rozado, Motoki) own that
            row. Our factorial-regression methodology with a years-of-experience-equivalent
            metric is a complement, not a stand-alone contribution.
          </p>
          <p>
            <strong>Finding 1 (the refusal cliff) is the new headline.</strong> No
            existing group has published on the structural refusal cliff at the
            factual / interpretive boundary — see{" "}
            <a
              href="/preview/refusal-cliff"
              className="underline decoration-zinc-400 underline-offset-4 hover:text-zinc-900 dark:hover:text-zinc-100"
            >
              /preview/refusal-cliff
            </a>{" "}
            for the result itself.
          </p>
          <p>
            <strong>§§3–5 are where the risk is.</strong> The yellow halos on rows
            7–8 (persona × pressure) and row 9 (cross-axis) depend on pilots
            landing. If the pilots fail or produce uninformative results, the
            paper&rsquo;s claim narrows to row 5 (refusal cliff) alone. Worth deciding
            Friday whether that&rsquo;s an acceptable risk profile.
          </p>
        </section>

        <footer className="pt-8 border-t border-zinc-200 dark:border-zinc-800 text-xs text-zinc-500 dark:text-zinc-400">
          This page is intentionally unlinked from the public site and excluded from
          robots. The matrix is editorial — generated from a hand-curated dictionary
          in <code className="font-mono">analysis/landscape_figure.py</code>, not from
          a citation database. Push back on any cell that looks wrong.
        </footer>
      </div>
    </main>
  );
}
