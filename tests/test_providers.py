"""Credential routing must preserve the model and its cross-vendor judge."""

import pytest

from p3.providers import CLAUDE_HAIKU, CLAUDE_SONNET, GPT_FLAGSHIP, pick_judge, resolve


@pytest.fixture(autouse=True)
def clean_provider_env(monkeypatch):
    for key in (
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY",
        "TOGETHER_API_KEY", "P3_OPENAI_JUDGE", "P3_ANTHROPIC_JUDGE",
    ):
        monkeypatch.delenv(key, raising=False)


def test_anthropic_subject_uses_openrouter_gpt_judge(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    assert pick_judge(CLAUDE_SONNET).id == f"openrouter/{GPT_FLAGSHIP.id}"


@pytest.mark.parametrize("vendor", ["anthropic", "openai"])
def test_gateway_does_not_hide_subject_vendor(monkeypatch, vendor):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    subject = resolve(f"openrouter/{vendor}/test-model")
    assert pick_judge(subject).vendor != subject.vendor


def test_direct_openai_key_keeps_existing_route(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    assert pick_judge(CLAUDE_SONNET) == GPT_FLAGSHIP


def test_single_vendor_fallback_still_warns(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    with pytest.warns(UserWarning, match="same-provider"):
        assert pick_judge(CLAUDE_SONNET) == CLAUDE_HAIKU


def test_no_judge_key_fails_without_api_calls():
    with pytest.raises(RuntimeError, match="neither"):
        pick_judge(CLAUDE_SONNET)


def test_explicit_judge_override_requires_opposite_vendor(monkeypatch):
    monkeypatch.setenv("P3_OPENAI_JUDGE", "anthropic/claude-sonnet-4-6")
    with pytest.raises(ValueError, match="openai model vendor"):
        pick_judge(CLAUDE_SONNET)


def test_explicit_judge_override_is_used_verbatim(monkeypatch):
    monkeypatch.setenv("P3_OPENAI_JUDGE", "openrouter/openai/test-snapshot")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    assert pick_judge(CLAUDE_SONNET).id == "openrouter/openai/test-snapshot"


@pytest.mark.parametrize("spec", ["openrouter/gpt-4o", "openrouter//gpt-4o", "openrouter/openai/"])
def test_gateway_requires_vendor_and_model(spec):
    with pytest.raises(ValueError, match="openrouter/vendor/model"):
        resolve(spec)
