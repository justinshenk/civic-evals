"""Billing records must cover the whole run before replacing estimates."""
from types import SimpleNamespace as NS

import pytest

from analysis.usage import _reported_call_costs


def event(cost: object, tokens: int = 100, cache: str | None = None) -> NS:
    return NS(event="model", model="openrouter/openai/gpt-6.1-sol", cache=cache,
              output=NS(usage=NS(total_tokens=tokens)),
              call=NS(response={"usage": {"cost": cost}}))


def log(events: list[NS], total_tokens: int = 200) -> NS:
    return NS(samples=[NS(events=events)], stats=NS(model_usage={
        "openrouter/openai/gpt-6.1-sol": NS(total_tokens=total_tokens),
    }))


def test_complete_provider_cost_includes_cache_write_charges() -> None:
    result = _reported_call_costs(log([event(0.007206), event(0.005256)]))
    assert result["openrouter/openai/gpt-6.1-sol"] == pytest.approx(0.012462)


@pytest.mark.parametrize("missing_cost", [None, -1, float("nan"), True, "0.01"])
def test_incomplete_or_invalid_billing_does_not_understate_cost(missing_cost: object) -> None:
    assert _reported_call_costs(log([event(0.01), event(missing_cost)])) == {}


def test_partial_sample_logs_do_not_replace_full_run_cost() -> None:
    assert _reported_call_costs(log([event(0.01)])) == {}


def test_local_cache_reads_are_not_billed_again() -> None:
    result = _reported_call_costs(log([event(0.01), event(0.01, cache="read")], 100))
    assert result["openrouter/openai/gpt-6.1-sol"] == pytest.approx(0.01)
