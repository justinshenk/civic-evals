# civic_translation

**Status: demo.** Spanish reference translations have not been reviewed by a native speaker or a civic-translation specialist (e.g. NALEO, AAJC). Treat scoring as directional only. The eval needs a human-translation pass before any specific finding is cited.

Tests English-to-Spanish translation of US civic procedural content. Focus areas:

- **Terminology accuracy** — `voter` ↔ `votante`, `polling place` ↔ `centro de votación` / `lugar de votación`, `absentee ballot` ↔ `boleta de voto en ausencia` / `boleta postal`, `precinct` ↔ `distrito electoral`
- **Preservation of jurisdictional caveats** — `varies by state` ↔ `varía según el estado`
- **Register appropriate to civic / governmental content** — formal `usted`, not informal `tú`

## Why
The `limited_english_speaker` persona is one of our canonical seven; this eval directly tests whether civic content is rendered usefully for non-English-dominant voters, which is the high-stakes failure mode we should care about most.

## Scoring
- `rubric_judge` — only scorer; rubrics specify expected terminology and structure preservation
