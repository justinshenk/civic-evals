import { ScoreMatrix } from "./components/ScoreMatrix";
import { PersonaChart } from "./components/PersonaChart";
import { SubScorePanel } from "./components/SubScorePanel";
import { EvalCards } from "./components/EvalCards";
import { ModelCards } from "./components/ModelCards";
import { CalibrationPanel } from "./components/CalibrationPanel";
import { BaselinePanel } from "./components/BaselinePanel";
import { BiasPanel } from "./components/BiasPanel";
import { loadRollup } from "@/lib/rollup";

export default function Home() {
  const rollup = loadRollup();
  const empty = rollup.n_rows === 0;
  const generatedAt = rollup.generated_at
    ? new Date(rollup.generated_at).toLocaleString("en-US", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: "UTC",
      }) + " UTC"
    : "never";

  const stats = [
    { label: "answers graded", value: rollup.n_rows },
    { label: "tests", value: rollup.evals.length },
    { label: "AI models", value: rollup.providers.length },
    { label: "grading methods", value: rollup.scorers.length },
  ];

  return (
    <main className="flex-1 w-full">
      <div className="mx-auto max-w-6xl px-6 py-12 sm:py-16 space-y-14">
        <header className="relative isolate space-y-5">
          {/* decorative ombre wash behind the hero */}
          <div
            aria-hidden
            className="brand-blob pointer-events-none absolute -top-24 right-0 -z-10 h-72 w-72 rounded-full sm:h-96 sm:w-96"
          />
          <p className="inline-flex items-center gap-2 rounded-full border border-blue-200/70 bg-blue-50/70 px-3 py-1 text-xs font-medium uppercase tracking-widest text-blue-700 dark:border-blue-400/20 dark:bg-blue-500/10 dark:text-blue-300">
            CORDA · P3 · Civic Information Reliability
          </p>
          <h1 className="max-w-4xl text-4xl sm:text-5xl font-semibold tracking-tight leading-[1.08]">
            How reliably do LLMs answer{" "}
            <span className="ombre-text">civic questions?</span>
          </h1>
          <p className="max-w-3xl text-lg text-zinc-600 dark:text-zinc-300 leading-relaxed">
            We test whether AI chatbots give people accurate, even-handed answers to everyday
            questions about voting, elections, and public policy — and whether they own up to it
            when they don&rsquo;t know. Every score below runs from 0 to 1, where higher is better.
          </p>

          <div className="grid grid-cols-2 gap-3 pt-2 sm:max-w-2xl sm:grid-cols-4">
            {stats.map((s) => (
              <div
                key={s.label}
                className="card flex flex-col gap-0.5 px-4 py-3"
              >
                <span className="ombre-text text-2xl font-semibold tabular-nums">
                  {s.value}
                </span>
                <span className="text-xs uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
                  {s.label}
                </span>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1 text-sm text-zinc-500 dark:text-zinc-400">
            <span>
              updated{" "}
              <strong className="font-medium text-zinc-800 dark:text-zinc-200">{generatedAt}</strong>
            </span>
            <span aria-hidden className="text-blue-300 dark:text-blue-700">
              •
            </span>
            <a
              href="https://github.com/justinshenk/civic-evals"
              className="font-medium text-blue-700 underline decoration-blue-300 underline-offset-4 hover:text-blue-900 dark:text-blue-300 dark:hover:text-blue-200"
            >
              source on GitHub →
            </a>
          </div>
        </header>

        <section className="space-y-4">
          <SectionHeader
            title="The tests in this suite"
            hint="Each card is one test we put the chatbots through. Each targets a different way an answer about voting, elections, or policy can go wrong — getting a fact wrong, sounding sure about something it can't know, or refusing a perfectly fair question."
            details={
              <>
                Each eval is a folder under <code className="font-mono">evals/</code>; contributors
                copy <code className="font-mono">_template/</code> to start a new one. See{" "}
                <code className="font-mono">CONTRIBUTING.md</code>.
              </>
            }
          />
          <EvalCards rollup={rollup} />
        </section>

        {!empty && rollup.providers.length > 0 && (
          <section className="space-y-4">
            <SectionHeader
              title="The AI models we tested"
              hint="How each chatbot does across every test. The question that matters: could an ordinary person rely on this model for answers about voting and elections? Click any model for its full report card."
            />
            <ModelCards rollup={rollup} />
          </section>
        )}

        {empty ? (
          <EmptyState />
        ) : (
          <>
            <section className="space-y-4">
              <SectionHeader
                title="How the models score on each test"
                hint="Higher is better, and greener is better. Each column is a different way of grading the very same answers."
                details={
                  <>
                    Each cell is the mean 0–1 score for that test / grading-method pair. Filter to a
                    single model to see a 95% bootstrap confidence interval and the sample size;
                    hover any cell for its count.
                  </>
                }
              />
              <ScoreMatrix rollup={rollup} />
            </section>

            <section className="space-y-4">
              <SectionHeader
                title="Accurate, honest, or appropriately silent?"
                hint="We grade three things separately: Is the answer correct? Is the model appropriately confident instead of bluffing? And does it refuse only when it genuinely should? A model can be perfectly accurate yet dangerously overconfident — splitting these apart shows which."
                details={
                  <>
                    Scored by an AI judge from a different company than the model under test, so no
                    model grades its own homework. Bars show each test&rsquo;s average on that
                    dimension.
                  </>
                }
              />
              <SubScorePanel rollup={rollup} />
            </section>

            <section className="space-y-4">
              <SectionHeader
                title="Does the answer change depending on who's asking?"
                hint="We ask the very same questions while changing who appears to be asking — their politics, profession, language, or how urgently they need help. If the bars for a test differ a lot, the model is treating people differently. Those gaps are the failures that matter most."
                details={
                  <>
                    Each bar is the average score for one type of asker on one test, graded by the
                    AI rubric judge.
                  </>
                }
              />
              <PersonaChart rollup={rollup} />
            </section>

            {rollup.bias && rollup.bias.length > 0 && (
              <section className="space-y-4">
                <SectionHeader
                  title="Do the models lean one way politically?"
                  hint="We showed every model identical school-board candidates and changed only one thing: whether their platform was a Democratic-typical or Republican-typical set of positions — same budgets, same résumés. Every model rated the Democratic-leaning platform higher. The bar shows how big that tilt is."
                />
                <BiasPanel rollup={rollup} />
              </section>
            )}

            <section className="space-y-4">
              <SectionHeader
                title="Does the model know when it's guessing?"
                hint="When a model isn't sure, does it show it? A high score means its confidence is honest — it's more certain on the questions it actually gets right, and hedges on the ones it gets wrong. 0.5 is no better than a coin flip."
                details={
                  <>
                    Measured on the estimation (&ldquo;Fermi&rdquo;) tasks as the AUROC of (1 ÷
                    confidence-interval width) against whether the estimate landed within ±10% of the
                    truth — the calibration metric from LM-Polygraph (Vashurin et al., TACL 2025),
                    specialized to interval forecasts.
                  </>
                }
              />
              <CalibrationPanel rollup={rollup} />
            </section>

            <section className="space-y-4">
              <SectionHeader
                title="How these tests compare to standard benchmarks"
                hint="The same models, run on well-known public benchmarks, so you can see how the civic-information gaps stack up against each model's general ability."
                details={
                  <>
                    Pulled from UKGovernmentBEIS/inspect_evals and run with{" "}
                    <code className="font-mono">--limit</code>, so these are a comparison axis, not a
                    full leaderboard reproduction.
                  </>
                }
              />
              <BaselinePanel rollup={rollup} />
            </section>
          </>
        )}

        <footer className="pt-8 border-t border-blue-200/60 dark:border-blue-400/15 text-sm text-zinc-500 dark:text-zinc-400">
          <p>
            Built on{" "}
            <a
              href="https://inspect.aisi.org.uk/"
              className="text-blue-700 underline decoration-blue-300 underline-offset-4 dark:text-blue-300"
            >
              inspect-ai
            </a>
            . Source:{" "}
            <a
              href="https://github.com/justinshenk/civic-evals"
              className="text-blue-700 underline decoration-blue-300 underline-offset-4 dark:text-blue-300"
            >
              justinshenk/civic-evals
            </a>
            . Contributions welcome — see{" "}
            <a
              href="https://github.com/justinshenk/civic-evals/blob/main/CONTRIBUTING.md"
              className="text-blue-700 underline decoration-blue-300 underline-offset-4 dark:text-blue-300"
            >
              CONTRIBUTING.md
            </a>
            .
          </p>
        </footer>
      </div>
    </main>
  );
}

function SectionHeader({
  title,
  hint,
  details,
}: {
  title: string;
  hint: string;
  details?: React.ReactNode;
}) {
  return (
    <div className="flex gap-3">
      <span aria-hidden className="ombre-rule mt-1 w-1 shrink-0 rounded-full" />
      <div className="space-y-2 max-w-3xl">
        <h2 className="text-xl sm:text-2xl font-semibold tracking-tight">{title}</h2>
        <p className="text-[15px] text-zinc-600 dark:text-zinc-300 leading-relaxed">{hint}</p>
        {details && (
          <details className="group">
            <summary className="inline-flex w-fit cursor-pointer items-center gap-1.5 rounded-full border border-blue-200/70 bg-blue-50/60 px-2.5 py-1 text-xs font-medium text-blue-700 list-none [&::-webkit-details-marker]:hidden hover:bg-blue-100/70 dark:border-blue-400/20 dark:bg-blue-500/10 dark:text-blue-300 dark:hover:bg-blue-500/20">
              <span aria-hidden className="transition-transform group-open:rotate-90">
                ▸
              </span>
              Technical details
            </summary>
            <div className="mt-2 rounded-lg border border-blue-200/50 bg-blue-50/30 px-3 py-2.5 text-xs leading-relaxed text-zinc-600 dark:border-blue-400/15 dark:bg-blue-500/5 dark:text-zinc-400">
              {details}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="panel border-dashed p-10 text-center">
      <p className="text-zinc-700 dark:text-zinc-300 font-medium">No results yet.</p>
      <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400 max-w-lg mx-auto">
        Run an eval, then regenerate the rollup:
        <br />
        <code className="font-mono text-xs bg-zinc-100 dark:bg-zinc-900 rounded px-2 py-1 mt-3 inline-block">
          uv run inspect eval evals/voting_access/eval.py --model anthropic/claude-haiku-4-5 --log-dir logs/
        </code>
        <br />
        <code className="font-mono text-xs bg-zinc-100 dark:bg-zinc-900 rounded px-2 py-1 mt-2 inline-block">
          uv run python analysis/rollup.py logs/ --format json -o site/public/data/rollup.json
        </code>
      </p>
    </div>
  );
}
