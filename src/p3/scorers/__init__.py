"""Shared scorer library. All scorers return the standard inspect-ai
``Score`` shape so the rollup layer stays scorer-agnostic.
"""

from p3.scorers.citation import citation_verifiability
from p3.scorers.consistency import consistency_across_paraphrases
from p3.scorers.fermi import fermi_calibration
from p3.scorers.ground_truth import ground_truth_match
from p3.scorers.refusal import appropriate_refusal
from p3.scorers.rubric_judge import rubric_judge

__all__ = [
    "ground_truth_match",
    "rubric_judge",
    "consistency_across_paraphrases",
    "appropriate_refusal",
    "citation_verifiability",
    "fermi_calibration",
]
