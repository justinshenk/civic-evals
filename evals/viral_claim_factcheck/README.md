# viral_claim_factcheck

**Status: demo.** Claims here are illustrative composites of widely-circulated patterns, not verbatim quotes from specific viral posts. Treat as scaffolding; before any score is cited as evidence about a specific claim, the original viral source should be re-checked.

Companion to `election_integrity`, focused on shorter-cycle, time-pinned claims. Tests whether the model:
- correctly identifies false viral claims with explanation
- doesn't over-reject true claims that *sound* viral
- acknowledges when a claim is current-events territory and needs an authoritative source check

## Scoring
- `rubric_judge` — primary; rubrics specify the expected verdict and the reasoning structure
- `appropriate_refusal` — secondary; tasks set `refusal_expected = answer` since over-refusal is itself a failure
