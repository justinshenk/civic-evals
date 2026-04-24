"""Model factory and judge-selection policy.

``inspect-ai`` already accepts ``"anthropic/claude-sonnet-4-6"``-style
model strings. This module exists to (a) name the canonical models used
across the suite so eval code doesn't hardcode version strings, (b) pick
a judge provider different from the subject to avoid same-model self-bias
in rubric scoring, and (c) fail loudly when required env vars are missing.
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


# Canonical model set. Bump version strings here and every eval picks up the change.
CLAUDE_SONNET = Model("anthropic", "claude-sonnet-4-6")
CLAUDE_HAIKU = Model("anthropic", "claude-haiku-4-5")
GPT_FLAGSHIP = Model("openai", "gpt-4o")
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
    """
    preferred = GPT_FLAGSHIP if subject.provider == "anthropic" else CLAUDE_SONNET
    if os.environ.get(_ENV_KEY[preferred.provider]):
        return preferred

    import warnings
    # Same-provider fallback. For Anthropic subject we use Haiku (cheaper,
    # still a different model than Sonnet) rather than the subject itself.
    fallback = CLAUDE_HAIKU if subject.provider == "anthropic" else CLAUDE_SONNET
    warnings.warn(
        f"pick_judge: {_ENV_KEY[preferred.provider]} not set; falling back "
        f"to same-provider judge {fallback.id}. Cross-provider judging is "
        "the default to avoid self-bias — set the other provider's key "
        "for flagship runs.",
        stacklevel=2,
    )
    return fallback
