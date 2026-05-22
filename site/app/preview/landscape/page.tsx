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

        <section className="space-y-4 pt-4 border-t border-zinc-200 dark:border-zinc-800">
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">
            Three CAIS-style variations under consideration
          </h2>
          <p className="text-sm text-zinc-700 dark:text-zinc-300">
            CAIS&rsquo;s contributions are <em>methodological</em>: paired-prompt contrastive
            design + consistency-as-metric. Those moves transfer to other variables and
            other output channels. Three concrete variations are below; together they
            shore up the yellow-halo rows above so the paper&rsquo;s novelty isn&rsquo;t
            single-observation-dependent.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-zinc-300 dark:border-zinc-700 text-left">
                  <th className="py-2 pr-3 font-medium">Topic row (from matrix above)</th>
                  <th className="py-2 px-2 font-medium text-center">
                    A · Covert refusal bias
                  </th>
                  <th className="py-2 px-2 font-medium text-center">
                    B · Multi-turn drift
                  </th>
                  <th className="py-2 px-2 font-medium text-center">
                    C · Frame curation
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="py-2 pr-3">Substantive policy bias (answer-side)</td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400">
                    ★ partial
                  </td>
                  <td className="py-2 px-2 text-center text-zinc-300 dark:text-zinc-700">
                    —
                  </td>
                  <td className="py-2 px-2 text-center text-zinc-300 dark:text-zinc-700">
                    —
                  </td>
                </tr>
                <tr className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="py-2 pr-3">Refusal / abstention as object of study</td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400 font-semibold">
                    ★ main
                  </td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400">
                    ★ partial
                  </td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400">
                    ★ partial
                  </td>
                </tr>
                <tr className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="py-2 pr-3">Persona conditioning of responses</td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400 font-semibold">
                    ★ main
                  </td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400">
                    ★ partial
                  </td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400 font-semibold">
                    ★ main
                  </td>
                </tr>
                <tr className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="py-2 pr-3">Multi-turn / sycophancy dynamics</td>
                  <td className="py-2 px-2 text-center text-zinc-300 dark:text-zinc-700">
                    —
                  </td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400 font-semibold">
                    ★ main
                  </td>
                  <td className="py-2 px-2 text-center text-zinc-300 dark:text-zinc-700">
                    —
                  </td>
                </tr>
                <tr className="border-b border-zinc-100 dark:border-zinc-900">
                  <td className="py-2 pr-3">Persona × pressure interaction</td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400">
                    ★ partial
                  </td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400 font-semibold">
                    ★ main
                  </td>
                  <td className="py-2 px-2 text-center text-zinc-300 dark:text-zinc-700">
                    —
                  </td>
                </tr>
                <tr>
                  <td className="py-2 pr-3">Cross-axis failure concentration</td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400">
                    ★ partial
                  </td>
                  <td className="py-2 px-2 text-center text-amber-700 dark:text-amber-400">
                    ★ partial
                  </td>
                  <td className="py-2 px-2 text-center text-zinc-300 dark:text-zinc-700">
                    —
                  </td>
                </tr>
              </tbody>
            </table>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-2">
              ★ main = the proposal&rsquo;s headline target. ★ partial = the proposal
              produces secondary evidence on that row.
            </p>
          </div>

          {/* Proposal A */}
          <article className="space-y-3 pt-4">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              A · &ldquo;Covert refusal bias&rdquo; — persona-contrastive pairs on the refusal
              channel <span className="text-amber-700 dark:text-amber-400">(strongest)</span>
            </h3>
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              CAIS doesn&rsquo;t study refusal as an object. Our refusal-cliff finding says
              interpretive civic questions get ~95% refusal — but{" "}
              <strong>is that 95% uniform across persona variants of the same question?</strong>
            </p>
            <ul className="text-sm text-zinc-700 dark:text-zinc-300 list-disc list-outside ml-5 space-y-1">
              <li>
                <strong>Vary</strong>: persona attributes (age, political-lean cue,
                profession, language fluency, jurisdiction) holding question content
                constant.
              </li>
              <li>
                <strong>Measure</strong>: refusal rate per persona pair, plus stance +
                frame on the non-refusing minority.
              </li>
              <li>
                <strong>Statistical test</strong>: McNemar / chi-squared on refusal
                across paired personas for each question.
              </li>
              <li>
                <strong>Null</strong>: cliff is uniform — refusal ≈ same rate across
                personas for substantively equivalent questions.
              </li>
              <li>
                <strong>Alt 1</strong>: refusal is asymmetric — the model refuses some
                personas more than others (epistemic-agency failure on the abstention
                dimension).
              </li>
              <li>
                <strong>Alt 2</strong>: refusal rate is symmetric but{" "}
                <em>shape</em> differs — when the model does engage, it gives different
                framings, sources, and action-recommendations to different personas.
              </li>
            </ul>
            <div className="overflow-x-auto pt-1">
              <table className="text-xs w-full border-collapse">
                <tbody className="font-mono">
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Questions
                    </td>
                    <td className="py-1">
                      5 interpretive items from{" "}
                      <code className="font-mono">openendedness_ladder</code> r3
                    </td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Personas
                    </td>
                    <td className="py-1">
                      4 from{" "}
                      <code className="font-mono">p3.lib.persona_sweep</code>{" "}
                      canonical set
                    </td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Providers
                    </td>
                    <td className="py-1">claude-haiku-4-5 + gpt-4o</td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Epochs / cell
                    </td>
                    <td className="py-1">10</td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Total generations
                    </td>
                    <td className="py-1">5 × 4 × 2 × 10 = 400</td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Cost
                    </td>
                    <td className="py-1">~$5–10 at current Haiku/GPT-4o pricing</td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Time
                    </td>
                    <td className="py-1">~1 day end-to-end</td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Scorer
                    </td>
                    <td className="py-1">
                      reuse{" "}
                      <code className="font-mono">multi_signal_extraction</code>{" "}
                      (refusal + stance + frame)
                    </td>
                  </tr>
                  <tr>
                    <td className="py-1 pr-3 font-sans text-zinc-500 dark:text-zinc-400">
                      Headline metric
                    </td>
                    <td className="py-1">
                      fraction of interpretive questions with significant refusal
                      asymmetry across personas
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              If headline &gt; ~20% → paper finding. If &lt; ~5% → we publish the
              null, which itself contributes to the &ldquo;refusal cliff is structural&rdquo;
              story.
            </p>
          </article>

          {/* Proposal B */}
          <article className="space-y-3 pt-4">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              B · Multi-turn drift contrastive pairs
            </h3>
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              CAIS measures consistency <em>within</em> a single response pair. We
              measure consistency <em>across turns under sycophantic pressure</em>.
            </p>
            <ul className="text-sm text-zinc-700 dark:text-zinc-300 list-disc list-outside ml-5 space-y-1">
              <li>
                <strong>Pair</strong>: same persona, same starting question, but one
                trajectory adds sycophantic pressure across N turns and the other
                doesn&rsquo;t.
              </li>
              <li>
                <strong>Measure</strong>: stance drift magnitude, refusal flip rate,
                frame migration across turns.
              </li>
              <li>
                <strong>Headline</strong>: &ldquo;models that hold position at t=0 abandon
                it under conversational pressure; drift magnitude is larger for some
                personas than others.&rdquo;
              </li>
              <li>
                Operationalizes Eric&rsquo;s #1 failure-mode idea (sycophancy → extremism)
                in CAIS-style methodology. Lands in §4 and provides the demo material
                for the funder-pitch story.
              </li>
            </ul>
          </article>

          {/* Proposal C */}
          <article className="space-y-3 pt-4">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              C · Frame-distribution contrastive pairs{" "}
              <span className="text-zinc-500 dark:text-zinc-400">
                (cheapest pilot, weakest standalone claim)
              </span>
            </h3>
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              Within the refusal envelope, models still pick <em>which</em> framing to
              refuse-shape into (e.g.,{" "}
              <code className="font-mono">turnout</code> vs{" "}
              <code className="font-mono">fraud_prevention</code> vs{" "}
              <code className="font-mono">equity</code>). The openendedness_ladder
              already extracts this via{" "}
              <code className="font-mono">multi_signal_extraction</code>.
            </p>
            <ul className="text-sm text-zinc-700 dark:text-zinc-300 list-disc list-outside ml-5 space-y-1">
              <li>
                <strong>Vary</strong>: persona or political-lean cue in the question.
              </li>
              <li>
                <strong>Measure</strong>: frame-distribution divergence (KL or χ²)
                across paired prompts.
              </li>
              <li>
                <strong>Headline</strong>: &ldquo;the model curates <em>which</em>{" "}
                framings it surfaces by persona, even when it formally refuses to take a
                position.&rdquo;
              </li>
              <li>
                Uses existing infrastructure — could be a pilot in days, not weeks.
                Weakest of the three because frame asymmetry is less directly an
                epistemic-agency claim than refusal asymmetry.
              </li>
            </ul>
          </article>

          {/* Differentiation */}
          <article className="space-y-3 pt-4">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              Why these are differentiated from CAIS, not derivative
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="border-b border-zinc-300 dark:border-zinc-700 text-left">
                    <th className="py-2 pr-3 font-medium">Dimension</th>
                    <th className="py-2 px-2 font-medium">CAIS</th>
                    <th className="py-2 px-2 font-medium">Proposals here</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-2 pr-3">Object of measurement</td>
                    <td className="py-2 px-2">Substantive bias on answer</td>
                    <td className="py-2 px-2">Refusal / drift / frame on interpretive Qs</td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-2 pr-3">Varied factor</td>
                    <td className="py-2 px-2">Policy-direction coding</td>
                    <td className="py-2 px-2">Persona attributes / conversational pressure</td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-2 pr-3">Output channel</td>
                    <td className="py-2 px-2">Sentiment + helpfulness consistency</td>
                    <td className="py-2 px-2">Refusal rate + stance drift + frame distribution</td>
                  </tr>
                  <tr className="border-b border-zinc-100 dark:border-zinc-900">
                    <td className="py-2 pr-3">Contribution</td>
                    <td className="py-2 px-2">Training fix (PCT)</td>
                    <td className="py-2 px-2">Audit + measurement; no training proposed</td>
                  </tr>
                  <tr>
                    <td className="py-2 pr-3">Citation move</td>
                    <td className="py-2 px-2">Foundational</td>
                    <td className="py-2 px-2">&ldquo;Extends CAIS-style contrastive design to the abstention dimension&rdquo;</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Different object, different variable, different output channel,
              complementary contribution. The team can cite CAIS as the methodological
              precedent — honest credit — while owning the dimension they didn&rsquo;t
              study.
            </p>
          </article>

          {/* How they fit the paper */}
          <article className="space-y-3 pt-4">
            <h3 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
              How they slot into the paper
            </h3>
            <ul className="text-sm text-zinc-700 dark:text-zinc-300 list-disc list-outside ml-5 space-y-2">
              <li>
                <strong>Proposal A</strong> becomes the methodological backbone of{" "}
                <strong>§3a (refusal channel)</strong> — persona contrastive pairs →
                &ldquo;covert refusal bias&rdquo; metric.
              </li>
              <li>
                <strong>§3b (substance channel)</strong> keeps the factorial
                regression from <code className="font-mono">multi_model_bias.py</code> with
                persona as a factor. So §3 ends up two-part.
              </li>
              <li>
                <strong>Proposal B</strong> lands in <strong>§4</strong> and feeds{" "}
                <strong>§5 (persona × pressure)</strong> if personas are varied in the
                pilot.
              </li>
              <li>
                <strong>Proposal C</strong> is the fallback if A&rsquo;s pilot lands
                weakly — it provides secondary evidence on the same row (persona
                conditioning) at much lower cost.
              </li>
            </ul>
          </article>
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
