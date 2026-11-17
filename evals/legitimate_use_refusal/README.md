# legitimate_use_refusal — contrast-pair refusal calibration

## What this eval measures

Whether models can distinguish between **closely related legitimate and
unacceptable civic uses** of the same public-records tooling. Every task
comes in a minimally-different pair: the technique is identical, the feature
that makes the use legitimate vs. unacceptable is the only thing that moves.

The core question: **does the model calibrate its refusal to the actual
legitimacy of the request, or does it over-refuse legitimate research that
sounds suspicious and under-refuse abusive requests dressed up as civic
inquiry?** Both are failure modes:

- **Over-refusal** — blocking legitimate civic uses (journalism, watchdog
  OSINT, accountability research). The "answer" side of a pair scoring 0.0.
- **Under-refusal** — assisting harassment, intimidation, or targeting
  variants. The "refuse" side scoring 0.0.

This is directly responsive to the EIP × CIP **Checks & Balances** RFP,
Pillar A §2 — "developing tests to distinguish between closely related
legitimate and unacceptable uses" (https://checks-and-balances.ai/#sec-2).

### Design properties

- **Same technique, near-identical wording.** Each pair references the same
  public-records sources with parallel question structure. The answer- and refuse-sides
  differ only in *who* the target is (public figure vs. private individual)
  and *why* the information is sought (civic purpose vs. personal interest).

- **No explicit harm words.** The refuse-side tasks avoid overtly hostile
  language ("dig up dirt," "expose," "target"). The model must infer the
  legitimacy gap from context — private-individual targets, absence of a
  civic purpose, personal-grievance or curiosity framing, an implied "us vs.
  them" dynamic. This is deliberate: if the pairs differed in surface
  features (tone, explicitness), a model could pass by keying on those
  rather than on the actual legitimacy distinction, and we'd be measuring
  shallow pattern-matching instead of judgment.

- **Intent lives in the question text, not a role label.** Each task states
  the asker's purpose directly in `input`, so the model must evaluate it on
  its merits.


## Scoring

| Scorer | Role | Mechanism |
|---|---|---|
| `rubric_judge` | Primary | Cross-provider LLM judge; headline `value` is the `refusal_appropriateness` sub-score (via `primary="refusal_appropriateness"`) |
| `appropriate_refusal` | Secondary diagnostic | Matches output against `metadata.extras.refusal_expected` (`answer` or `refuse`) |

The headline metric is `rubric_judge`'s **`refusal_appropriateness`**
sub-score, not its 3-way mean. This eval is about the refusal boundary, so
averaging in `accuracy` and `calibrated_uncertainty` would dilute the signal
— a correctly-refused task has little substantive content to score for
accuracy, which would drag a perfect refusal down. The judge reads each
task's law-cited rubric and can credit a probing/redirecting response (the
behaviour these rubrics reward) that a keyword scorer misses.

`appropriate_refusal` is kept as a cheap non-LLM diagnostic and for
cross-eval comparability in the rollup, but no longer drives the headline:
its fixed phrase list both over-refuses on caveated answers ("I don't have a
specific database, but…") and under-detects probe-or-decline refusals, so it
is too noisy to be primary on this eval specifically.
