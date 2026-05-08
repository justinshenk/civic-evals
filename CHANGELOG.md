# Changelog

All notable changes to this project are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versioning is
calendar-based per merge wave (no semver — this is a research suite,
not a public API).

## [Unreleased]

### Fixed
- **Schema**: tasks setting both `target` and `rubric` are now rejected at load
  time. The loader writes `target` into `Sample.target` and `rubric` into
  metadata, so a task with both would silently drop one branch downstream.
  Now fails loudly. (`src/p3/schemas.py`)
- **Calibration AUROC reconstruction**: when re-deriving `point_score` from raw
  `(truth, estimate)` for historical logs that lack `sub_scores.point_score`,
  the linear decay branch was clamping all `rel > 1.0` to zero. The live fermi
  scorer applies an exponential-decay tail past 100% relative error; the
  reconstruction now mirrors that. Existing AUROC numbers over historical
  logs may shift slightly. (`analysis/rollup.py`)
- **Slack summary provider means**: per-(eval, provider) means now exclude rows
  with `score_metadata.parse_success == False`. The token-logprob scorer
  returns `value=0.0` as a sentinel on Anthropic (which doesn't expose token
  logprobs), and the prior aggregation included that sentinel — dragging
  Anthropic's mean down for cosmetic reasons unrelated to capability.
  (`analysis/slack_summary.py`)
- **`pick_judge` setup-time failure**: when both the preferred and fallback
  judge API keys are missing, raise `RuntimeError` at setup instead of
  deferring the crash to mid-eval inside the scorer. (`src/p3/providers.py`)
- **Consistency scorer JSON parser**: a malformed substring matched by the
  brace regex no longer raises `JSONDecodeError`. Falls back to singleton
  clusters per the documented graceful-degradation contract.
  (`src/p3/scorers/consistency.py`)
- **AUROC explanation string**: corrected the "within ±10%" phrasing to
  describe the full coverage of the `point_score >= 0.9` threshold (~±19% of
  truth, since the threshold straddles the linear-decay region).
  (`analysis/rollup.py`)

## 2026-05-08

### Added
- **Staleness LLM judge** ([#8](https://github.com/justinshenk/civic-evals/pull/8)):
  replaces the regex phrase list (deleted) with a Haiku judge that classifies
  failures as `cutoff` / `source` / `variation` / `none` with verbatim
  evidence quotes. Disk-cached at `analysis/.staleness_cache.json` so reruns
  over unchanged completions are free. Skips search-enabled evals (those
  should cite, not hedge — `citation_verifiability` covers them). Graceful
  no-op when no API key is set, so CI offline rollups keep working.
- **Failure surfacing with staleness split**
  ([#6](https://github.com/justinshenk/civic-evals/pull/6) →
  superseded by #8): per-difficulty alarm thresholds (`easy < 0.9`,
  `medium < 0.7`); a "Worth a closer look" panel on every eval detail page;
  a `python analysis/failures.py` CLI that prints a paste-ready markdown
  report with the staleness ack-rate up top.
- **Information-density scorer** for `policy_impact_personalization`
  ([#5](https://github.com/justinshenk/civic-evals/pull/5)): three sub-scores
  orthogonal to factual accuracy — `actionability`,
  `specificity_calibration`, `persuasion_pressure`. Anchored in the
  [behavior-in-the-wild persuasion taxonomy](https://behavior-in-the-wild.github.io/measure-persuasion).
- **Web-search variant** for `policy_impact_personalization` (#5):
  `eval_with_search.py` exposes a `web_search()` tool with a cite-or-say-
  no-source contract. Promoted `citation_verifiability` from `EXPERIMENTAL`
  to the production scorer set. Opt-in; not part of the weekly
  `refresh-results` action.
- **Persona ablation variants** for `ei-001`, `ei-006`, `ei-011`, `ei-012`
  ([#4](https://github.com/justinshenk/civic-evals/pull/4)).

### Changed
- `analysis/rollup.py` now auto-loads `.env` from the repo root so the
  staleness judge can pick up `ANTHROPIC_API_KEY` the same way `inspect
  eval` does.

### Removed
- `analysis/cutoff_check.py` (regex phrase list, replaced by the LLM judge in
  #8).

## 2026-04 (earlier)

Initial scaffolding: shared schemas, persona slot, scorer library
(`rubric_judge`, `appropriate_refusal`, `ground_truth_match`,
`fermi_calibration`, `token_logprob_uncertainty`), `analysis/rollup.py`,
Next.js dashboard, GitHub Actions for `refresh-results` (weekly + manual)
and CI (lint + schema + smoke), and the three reference evals
(`voting_access`, `election_integrity`, `policy_impact_personalization`)
plus `fermi_civic_estimation`. See `git log` for granular history.
