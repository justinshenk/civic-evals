# policy_position_comparison

**Status: demo.** Topic selection and rubric framings are illustrative — they have not been reviewed by domain experts on either side. Treat any partisan-asymmetry finding as preliminary signal that needs replication, not conclusion.

Tasks come in **symmetry pairs**: same policy area, mirrored partisan framings. The metric we actually care about is the per-pair score gap — large gaps mean the model (or our judge) treats one framing more sympathetically than the other.

## Pairs
- `ppc-001` / `ppc-002` — voting access
- `ppc-003` / `ppc-004` — campaign finance
- `ppc-005` / `ppc-006` — election security

Generalizes the mechanism we built into `election_integrity` for the ei-011 / ei-012 pair.

## Scoring
- `rubric_judge` — only scorer; rubrics are designed to require neutral handling regardless of framing
