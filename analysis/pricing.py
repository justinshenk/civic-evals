"""Per-model API pricing for cost reconstruction.

inspect-ai records exact ``ModelUsage`` (input/output/reasoning tokens)
on every eval log, and some providers also report ``total_cost``
directly. For providers that *don't* report cost we fall back to this
table — a small per-model $/Mtok lookup.

The table is intentionally short: only models actually used by this
suite (the canonical providers in ``src/p3/providers.py`` plus the
OpenRouter set used by ``analysis/multi_model_bias.py``). When you add
a new model, add a row here too — ``cost_for_usage`` returns ``None``
for unknown models and the CLI will warn.

Prices are approximate and need periodic review; ``LAST_REVIEWED``
records when the table was last touched. Vendor pricing pages are the
source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass

LAST_REVIEWED = "2026-05-08"


@dataclass(frozen=True)
class Price:
    """USD per 1M tokens. Cache rates default to the input rate when the
    provider doesn't publish a separate cached-read price."""

    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float | None = None
    cache_write_per_mtok: float | None = None
    reasoning_per_mtok: float | None = None  # falls back to output rate

    def cost(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int | None = None,
        cache_write_tokens: int | None = None,
        reasoning_tokens: int | None = None,
    ) -> float:
        per = lambda n, rate: (n or 0) * rate / 1_000_000  # noqa: E731
        cost = per(input_tokens, self.input_per_mtok) + per(
            output_tokens, self.output_per_mtok
        )
        if cache_read_tokens:
            cost += per(
                cache_read_tokens,
                self.cache_read_per_mtok
                if self.cache_read_per_mtok is not None
                else self.input_per_mtok,
            )
        if cache_write_tokens:
            cost += per(
                cache_write_tokens,
                self.cache_write_per_mtok
                if self.cache_write_per_mtok is not None
                else self.input_per_mtok,
            )
        if reasoning_tokens:
            # Anthropic extended-thinking and OpenAI reasoning tokens are
            # billed at output rate unless the provider lists otherwise.
            cost += per(
                reasoning_tokens,
                self.reasoning_per_mtok
                if self.reasoning_per_mtok is not None
                else self.output_per_mtok,
            )
        return cost


# Canonical models used by the suite. Keys match inspect-ai's
# ``provider/model`` form (the same string that appears in eval logs as
# ``log.eval.model``). Approximate USD/Mtok as of LAST_REVIEWED.
_PRICES: dict[str, Price] = {
    # --- Anthropic ---
    "anthropic/claude-sonnet-4-6": Price(3.00, 15.00, cache_read_per_mtok=0.30, cache_write_per_mtok=3.75),
    "anthropic/claude-haiku-4-5": Price(1.00, 5.00, cache_read_per_mtok=0.10, cache_write_per_mtok=1.25),
    # --- OpenAI ---
    "openai/gpt-4o": Price(2.50, 10.00, cache_read_per_mtok=1.25),
    "openai/gpt-4o-mini": Price(0.15, 0.60, cache_read_per_mtok=0.075),
    # --- Together (open-weights) ---
    "together/meta-llama/Llama-3.3-70B-Instruct-Turbo": Price(0.88, 0.88),
    # --- OpenRouter (cross-provider proxy used by multi_model_bias.py).
    # Rates here are OpenRouter's pass-through pricing for each model. ---
    "openrouter/anthropic/claude-haiku-4.5": Price(1.00, 5.00),
    "openrouter/openai/gpt-4o-mini": Price(0.15, 0.60),
    "openrouter/google/gemini-2.5-flash": Price(0.30, 2.50),
    "openrouter/meta-llama/llama-3.3-70b-instruct": Price(0.88, 0.88),
    "openrouter/deepseek/deepseek-chat": Price(0.27, 1.10),
    "openrouter/qwen/qwen-2.5-72b-instruct": Price(0.40, 0.40),
}


def price_for(model: str) -> Price | None:
    """Look up a model. Tolerates trailing-suffix variants like
    ``anthropic/claude-haiku-4-5-20251001`` by stripping the date tail.
    """
    if model in _PRICES:
        return _PRICES[model]
    # Strip a trailing date stamp, e.g. ``-20251001``.
    base = model.rsplit("-", 1)[0]
    if base in _PRICES:
        return _PRICES[base]
    return None


def cost_for_usage(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    input_tokens_cache_read: int | None = None,
    input_tokens_cache_write: int | None = None,
    reasoning_tokens: int | None = None,
    reported_cost: float | None = None,
) -> tuple[float | None, str]:
    """Resolve a USD cost for one model's usage.

    Returns ``(cost, source)`` where source is:
      - ``"reported"``: the provider sent ``total_cost`` and we trust it.
      - ``"computed"``: we multiplied tokens by our price table.
      - ``"unknown"``: model not in price table and no reported cost; cost is ``None``.

    The two-source distinction lets the site footnote estimates so a
    reader can tell what's authoritative.
    """
    if reported_cost is not None:
        return reported_cost, "reported"
    price = price_for(model)
    if price is None:
        return None, "unknown"
    return (
        price.cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=input_tokens_cache_read,
            cache_write_tokens=input_tokens_cache_write,
            reasoning_tokens=reasoning_tokens,
        ),
        "computed",
    )


def known_models() -> list[str]:
    """For diagnostics — list the models the price table currently covers."""
    return sorted(_PRICES)
