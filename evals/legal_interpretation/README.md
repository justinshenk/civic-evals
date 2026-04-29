# legal_interpretation

**Status: demo.** Statute citations are real but task framings are illustrative; this is not legal advice and should not be cited as such. Rubrics emphasize the meta-question — does the model know when to redirect to a lawyer.

Federal election-law hypotheticals testing two skills:
1. **Knowing the statute** — what does Title 52 / 18 USC § 611 / 42 USC § 1973gg actually say
2. **Knowing when not to opine** — model should explain general framework but redirect specific situations to counsel

## Scoring
- `rubric_judge` — primary; rubrics specify both the legal-substance reward and the redirect-when-appropriate reward
- `appropriate_refusal` — secondary; some tasks expect the model to redirect (`refusal_expected = hedge`), others expect the model to answer the framework question (`refusal_expected = answer`)
