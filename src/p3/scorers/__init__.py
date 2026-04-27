"""Shared scorer library. All scorers return the standard inspect-ai
``Score`` shape so the rollup layer stays scorer-agnostic.

Scorers are split into two tiers:

- ``__all__`` — production-ready, used in at least one reference eval,
  exercised in tests, safe for mentees to copy-paste.
- ``EXPERIMENTAL`` — implementations that compile and have a clear
  contract but aren't currently wired into any eval and have no test
  coverage. Importing them works (``from p3.scorers import
  consistency_across_paraphrases``) but a PR that uses one should
  include both an eval that exercises it and tests for the new path.
"""

# Redundant-alias re-exports for the experimental tier — ruff F401-clean
# without adding them to __all__, which is the public-API contract.
from p3.scorers.citation import citation_verifiability as citation_verifiability
from p3.scorers.consistency import (
    consistency_across_paraphrases as consistency_across_paraphrases,
)
from p3.scorers.fermi import fermi_calibration
from p3.scorers.ground_truth import ground_truth_match
from p3.scorers.logprob import token_logprob_uncertainty
from p3.scorers.refusal import appropriate_refusal
from p3.scorers.rubric_judge import rubric_judge

__all__ = [
    "ground_truth_match",
    "rubric_judge",
    "appropriate_refusal",
    "fermi_calibration",
    "token_logprob_uncertainty",
]

# Implementations that aren't yet exercised by any eval. Kept importable
# so existing references don't break, but excluded from __all__ so
# ``from p3.scorers import *`` and the CONTRIBUTING.md scorer table
# reflect what's actually production-tested.
EXPERIMENTAL = (
    "consistency_across_paraphrases",
    "citation_verifiability",
)
