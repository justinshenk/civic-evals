"""Personas as orthogonal attribute vectors.

Fixed personas (``Maria, 34, teacher from Ohio``) feel realistic but make
ablation impossible — you cannot tell whether an effect came from age,
gender, profession, region, or the combination. Attribute vectors let us
vary one dimension at a time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

Role = Literal[
    "generic_citizen",
    "first_time_voter",
    "election_worker",
    "journalist",
    "elderly",
    "suppression_interested",
]
LangFluency = Literal["native", "fluent", "limited_english"]
Education = Literal["unspecified", "no_hs", "hs", "bachelors", "grad"]
PoliticalLean = Literal["unspecified", "left", "center", "right"]
Urgency = Literal["low", "medium", "high"]
DigitalLiteracy = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class Persona:
    role: Role = "generic_citizen"
    lang_fluency: LangFluency = "fluent"
    education: Education = "unspecified"
    political_lean: PoliticalLean = "unspecified"
    urgency: Urgency = "medium"
    digital_literacy: DigitalLiteracy = "medium"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)
