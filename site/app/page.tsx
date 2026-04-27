import { ScoreMatrix } from "./components/ScoreMatrix";
import { PersonaChart } from "./components/PersonaChart";
import { SubScorePanel } from "./components/SubScorePanel";
import { EvalCards } from "./components/EvalCards";
import { CalibrationPanel } from "./components/CalibrationPanel";
import { BaselinePanel } from "./components/BaselinePanel";
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

  return (
    <main className="flex-1 w-full">
      <div className="mx-auto max-w-6xl px-6 py-12 space-y-12">
        <header className="space-y-3">
          <p className="text-xs uppercase tracking-widest text-zinc-500 dark:text-zinc-400">
            CORDA · P3 · Civic Information Reliability
          </p>
          <h1 className="text-4xl font-semibold tracking-tight">
            How reliably do LLMs answer civic questions?
          </h1>
          <p className="max-w-3xl text-zinc-600 dark:text-zinc-400 leading-relaxed">
            An open evaluation suite measuring LLM reliability on voting access, election
            integrity, and persona-conditioned policy reasoning. Each eval runs against the same
            rubrics, scored for factual accuracy, calibrated uncertainty, and appropriate refusal.
          </p>
          <div className="flex flex-wrap gap-6 pt-2 text-sm text-zinc-500 dark:text-zinc-400">
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">{rollup.n_rows}</strong> rows
            </span>
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">{rollup.evals.length}</strong>{" "}
              evals
            </span>
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">{rollup.providers.length}</strong>{" "}
              providers
            </span>
            <span>
              <strong className="text-zinc-900 dark:text-zinc-100">{rollup.scorers.length}</strong>{" "}
              scorers
            </span>
            <span>
              updated{" "}
              <strong className="text-zinc-900 dark:text-zinc-100">{generatedAt}</strong>
            </span>
            <a
              href="https://github.com/justinshenk/civic-evals"
              className="underline decoration-zinc-400 underline-offset-4 hover:text-zinc-900 dark:hover:text-zinc-100"
            >
              source on GitHub →
            </a>
          </div>
        </header>

        <section className="space-y-4">
          <SectionHeader
            title="Evals in this suite"
            hint="Each eval is a folder under evals/. Mentees copy _template/ to start a new one — see CONTRIBUTING.md."
          />
          <EvalCards rollup={rollup} />
        </section>

        {empty ? (
          <EmptyState />
        ) : (
          <>
            <section className="space-y-4">
              <SectionHeader
                title="Mean score by eval × scorer"
                hint="Cell = mean of 0–1 scores for that eval/scorer pair. Hover for sample count."
              />
              <ScoreMatrix rollup={rollup} />
            </section>

            <section className="space-y-4">
              <SectionHeader
                title="Rubric sub-scores"
                hint="The rubric judge scores accuracy, calibrated uncertainty, and appropriate refusal separately. A model can be accurate and overconfident; these break it apart."
              />
              <SubScorePanel rollup={rollup} />
            </section>

            <section className="space-y-4">
              <SectionHeader
                title="Mean score by persona"
                hint="Same tasks, different personas. Gaps here are the reliability failures that matter most."
              />
              <PersonaChart rollup={rollup} />
            </section>

            <section className="space-y-4">
              <SectionHeader
                title="Calibration"
                hint="For Fermi tasks, AUROC of (1/CI-width) vs (point estimate within ±10% of truth). Mirrors the calibration AUROC reported by LM-Polygraph (Vashurin et al., TACL 2025), specialized to interval forecasts. 0.5 = chance; >0.75 = the model knows when it knows."
              />
              <CalibrationPanel rollup={rollup} />
            </section>

            <section className="space-y-4">
              <SectionHeader
                title="External baselines"
                hint="Pulled from UKGovernmentBEIS/inspect_evals and run with --limit, so these numbers are a comparison axis, not a leaderboard reproduction. Use them to calibrate how civic-eval gaps compare to model capability ceilings on established benchmarks."
              />
              <BaselinePanel rollup={rollup} />
            </section>
          </>
        )}

        <footer className="pt-8 border-t border-zinc-200 dark:border-zinc-800 text-sm text-zinc-500 dark:text-zinc-400">
          <p>
            Built on{" "}
            <a
              href="https://inspect.aisi.org.uk/"
              className="underline decoration-zinc-400 underline-offset-4"
            >
              inspect-ai
            </a>
            . Source:{" "}
            <a
              href="https://github.com/justinshenk/civic-evals"
              className="underline decoration-zinc-400 underline-offset-4"
            >
              justinshenk/civic-evals
            </a>
            . Contributions welcome — see{" "}
            <a
              href="https://github.com/justinshenk/civic-evals/blob/main/CONTRIBUTING.md"
              className="underline decoration-zinc-400 underline-offset-4"
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

function SectionHeader({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="space-y-1">
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-3xl">{hint}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="rounded-lg border border-dashed border-zinc-300 dark:border-zinc-700 p-10 text-center">
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
