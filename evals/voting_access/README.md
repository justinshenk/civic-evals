# voting_access

Procedural civic facts about voting in the United States: registration, identification requirements, polling places, ballot access, and election timing.

## Why this eval

Voting access questions have defensible, verifiable answers. If a model hallucinates a voter-ID requirement that doesn't exist in a jurisdiction, or invents a registration deadline, that's a direct harm — people may miss deadlines or be wrongly turned away.

The tasks split into:

- **Federal-level facts** — same answer in every state (26th Amendment, UOCAVA, federal-office ID rules).
- **Jurisdiction-dependent facts** — correct behavior is to say "it depends on state" and optionally surface the axis of variation. Tasks of this type set `metadata.refusal_expected = "hedge"`.

## Sources

- US Constitution (Amendments 15, 19, 24, 26)
- Uniformed and Overseas Citizens Absentee Voting Act (UOCAVA), 52 USC § 20301
- Help America Vote Act (HAVA) of 2002
- National Association of Secretaries of State (NASS) "Can I Vote" portal

State-level procedural specifics are deliberately scoped out of this reference eval — those belong in future state-specific evals with state-SoS citations.

## Scoring

- `ground_truth_match` on regex/substring for questions with a single defensible answer.
- `rubric_judge` for prose questions, with the rubric emphasizing calibrated uncertainty.
- `appropriate_refusal` for jurisdiction-dependent questions, expecting `"hedge"`.

## Known risks

- State-level rules change frequently. Do not extend this eval with state-specific facts without committing to a refresh cadence tied to election-cycle dates.
- The rubric judge may penalize correct hedging on jurisdiction-dependent questions. Mitigation: `appropriate_refusal` scores the hedge directly, independent of the rubric.
