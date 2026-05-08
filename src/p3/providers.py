"""Model factory and judge-selection policy.

``inspect-ai`` already accepts ``"anthropic/claude-sonnet-4-6"``-style
model strings. This module exists to (a) name the canonical models used
across the suite so eval code doesn't hardcode version strings, (b) pick
a judge provider different from the subject to avoid same-model self-bias
in rubric scoring, and (c) fail loudly when required env vars are missing.

**Version pinning.** Where vendors expose dated model aliases, the
canonical constants below pin to the dated form rather than the
floating short alias. This trades a manual bump cadence for measurement
reproducibility: when Anthropic or OpenAI ships an incremental version
under the same family name, the suite keeps measuring the *same model*
until a maintainer reviews and bumps the suffix. Without pinning, a
silent shift would conflate "the model changed" with "the suite found
different behavior" — bad for a benchmark that tracks model behavior
across time.

Bump policy: when a new dated suffix lands and a maintainer wants to
adopt it, edit the suffix here and re-run the full eval suite under
both versions before promoting. The resulting paired run is a clean
delta. analysis/pricing.py strips trailing date suffixes when looking
up prices, so the price table doesn't need parallel updates.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

ProviderName = Literal["anthropic", "openai", "together"]


@dataclass(frozen=True)
class Model:
    provider: ProviderName
    name: str

    @property
    def id(self) -> str:
        return f"{self.provider}/{self.name}"


# Canonical model set. Bump version strings here (see "Version pinning"
# in the module docstring for the bump policy) and every eval picks up
# the change.
#
# Sonnet 4.6 is currently aliased without a dated suffix — the API
# returns just "claude-sonnet-4-6" rather than a dated form, so the
# alias *is* the canonical pin until Anthropic ships a successor.
# Revisit when the next dated form appears in eval logs.
CLAUDE_SONNET = Model("anthropic", "claude-sonnet-4-6")
CLAUDE_HAIKU = Model("anthropic", "claude-haiku-4-5-20251001")
GPT_FLAGSHIP = Model("openai", "gpt-4o-2024-08-06")
LLAMA_OPEN = Model("together", "meta-llama/Llama-3.3-70B-Instruct-Turbo")

ALL_SUBJECTS: list[Model] = [CLAUDE_SONNET, GPT_FLAGSHIP, LLAMA_OPEN]

DEFAULT_SUBJECT = CLAUDE_SONNET
CI_SMOKE_MODEL = CLAUDE_HAIKU  # cheapest; used in smoke tests


_ENV_KEY: dict[ProviderName, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "together": "TOGETHER_API_KEY",
}


def require_env(model: Model) -> None:
    """Raise if the API key for ``model`` is not set."""
    key = _ENV_KEY[model.provider]
    if not os.environ.get(key):
        raise RuntimeError(
            f"Missing {key}. Set it in .env or your shell before running "
            f"evals against {model.id}."
        )


def resolve(spec: str | Model) -> Model:
    if isinstance(spec, Model):
        return spec
    provider, _, name = spec.partition("/")
    if not name:
        raise ValueError(f"Model spec {spec!r} must be 'provider/name'.")
    if provider not in _ENV_KEY:
        raise ValueError(f"Unknown provider {provider!r}. Valid: {sorted(_ENV_KEY)}")
    return Model(provider=provider, name=name)  # type: ignore[arg-type]


def pick_judge(subject: Model) -> Model:
    """Return a judge model from a *different* provider than ``subject``.

    Prevents the trivial self-bias where a model grades its own outputs
    favorably. If the subject is Claude, judge with GPT; if GPT, judge
    with Claude; if open-weights, judge with Claude (the strongest
    reasoner we have).

    Degrades gracefully: if the preferred judge's API key is not set,
    falls back to a same-provider judge and emits a warning. Mentees
    running against one provider at a time still get results, but the
    log entry records the degradation so it shows up in the rollup.

    Raises ``RuntimeError`` if neither the preferred nor the fallback
    judge has an API key set — failing at setup is far better than
    crashing mid-eval inside the scorer.
    """
    preferred = GPT_FLAGSHIP if subject.provider == "anthropic" else CLAUDE_SONNET
    if os.environ.get(_ENV_KEY[preferred.provider]):
        return preferred

    # Same-provider fallback. For Anthropic subject we use Haiku (cheaper,
    # still a different model than Sonnet) rather than the subject itself.
    fallback = CLAUDE_HAIKU if subject.provider == "anthropic" else CLAUDE_SONNET
    if not os.environ.get(_ENV_KEY[fallback.provider]):
        raise RuntimeError(
            f"pick_judge: neither {_ENV_KEY[preferred.provider]} (preferred "
            f"judge {preferred.id}) nor {_ENV_KEY[fallback.provider]} "
            f"(fallback {fallback.id}) is set. Set at least one provider's "
            "API key before running rubric-judged or information-density evals."
        )

    import warnings
    warnings.warn(
        f"pick_judge: {_ENV_KEY[preferred.provider]} not set; falling back "
        f"to same-provider judge {fallback.id}. Cross-provider judging is "
        "the default to avoid self-bias — set the other provider's key "
        "for flagship runs.",
        stacklevel=2,
    )
    return fallback
