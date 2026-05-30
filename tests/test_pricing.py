"""Pricing table + ``cost_for_usage`` semantics.

The cost numbers themselves drift with vendor pricing — these tests
don't pin specific dollar values. They pin the *shape*: reported beats
computed, unknown models return None, cache reads are billed at the
cache-read rate, reasoning tokens are billed at the output rate when
no specific reasoning rate exists, and the per-million math is right.
"""

from __future__ import annotations

import pytest

from analysis.pricing import (
    Price,
    cost_for_usage,
    known_models,
    price_for,
)


def test_price_for_known_model() -> None:
    p = price_for("anthropic/claude-haiku-4-5")
    assert p is not None
    assert p.input_per_mtok > 0
    assert p.output_per_mtok > p.input_per_mtok  # output is always pricier


def test_price_for_unknown_model_returns_none() -> None:
    assert price_for("synthetic/no-such-model") is None


def test_price_for_strips_date_suffix() -> None:
    """Anthropic returns ``claude-haiku-4-5-20251001`` style ids in
    eval logs; the price table is keyed on the canonical short form."""
    base = price_for("anthropic/claude-haiku-4-5")
    suffixed = price_for("anthropic/claude-haiku-4-5-20251001")
    assert base is not None and suffixed is not None
    assert suffixed == base


def test_cost_per_million_math() -> None:
    """1M input @ $1, 1M output @ $5 → exactly $6."""
    p = Price(input_per_mtok=1.0, output_per_mtok=5.0)
    assert p.cost(input_tokens=1_000_000, output_tokens=1_000_000) == pytest.approx(6.0)


def test_cost_for_usage_prefers_reported() -> None:
    cost, src = cost_for_usage(
        "anthropic/claude-haiku-4-5",
        input_tokens=1000,
        output_tokens=500,
        reported_cost=1.23,
    )
    assert cost == 1.23
    assert src == "reported"


def test_cost_for_usage_falls_back_to_computed() -> None:
    cost, src = cost_for_usage(
        "anthropic/claude-haiku-4-5",
        input_tokens=1_000_000,
        output_tokens=0,
    )
    assert src == "computed"
    # Whatever Haiku's input rate is, 1M tokens should equal exactly that.
    p = price_for("anthropic/claude-haiku-4-5")
    assert p is not None
    assert cost == pytest.approx(p.input_per_mtok)


def test_unknown_model_returns_none_cost() -> None:
    cost, src = cost_for_usage("synthetic/no-such-model", input_tokens=1000, output_tokens=500)
    assert cost is None
    assert src == "unknown"


def test_cache_read_uses_cache_rate_when_set() -> None:
    p = Price(input_per_mtok=10.0, output_per_mtok=50.0, cache_read_per_mtok=1.0)
    # 1M cache-read tokens at the cache rate is $1, not $10.
    assert p.cost(input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000) == pytest.approx(1.0)


def test_cache_read_falls_back_to_input_rate_when_not_set() -> None:
    """Providers that don't publish a cache-read price get charged the
    full input rate — the conservative assumption."""
    p = Price(input_per_mtok=10.0, output_per_mtok=50.0, cache_read_per_mtok=None)
    assert p.cost(input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000) == pytest.approx(10.0)


def test_reasoning_tokens_billed_at_output_rate_by_default() -> None:
    """Anthropic extended-thinking and OpenAI reasoning tokens bill at
    the output rate unless the price table specifies otherwise."""
    p = Price(input_per_mtok=1.0, output_per_mtok=5.0)
    assert p.cost(input_tokens=0, output_tokens=0, reasoning_tokens=1_000_000) == pytest.approx(5.0)


def test_known_models_list_is_nonempty_and_sorted() -> None:
    models = known_models()
    assert len(models) > 0
    assert models == sorted(models)
    # Sanity: at least the two canonical Anthropic models we test against.
    assert "anthropic/claude-haiku-4-5" in models
    assert "anthropic/claude-sonnet-4-6" in models


def test_zero_tokens_zero_cost() -> None:
    cost, src = cost_for_usage("anthropic/claude-haiku-4-5", input_tokens=0, output_tokens=0)
    assert cost == 0.0
    assert src == "computed"
