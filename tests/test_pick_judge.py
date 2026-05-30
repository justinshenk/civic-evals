"""``pick_judge`` env-var handling: degraded paths and the new failure mode.

The earlier implementation warned and fell back to a same-provider judge
without verifying the fallback's API key was set, deferring the crash
until the scorer's first ``get_model().generate()`` call mid-eval. The
preferred behavior is to fail at task-construction time so the operator
sees a clear, fixable error instead of a partial run with cryptic
inspect-ai stack traces.
"""

from __future__ import annotations

import warnings

import pytest

from p3.providers import (
    CLAUDE_HAIKU,
    CLAUDE_SONNET,
    GPT_FLAGSHIP,
    LLAMA_OPEN,
    pick_judge,
)


def _clear_keys(monkeypatch: pytest.MonkeyPatch, *keys: str) -> None:
    for k in keys:
        monkeypatch.delenv(k, raising=False)


def _set(monkeypatch: pytest.MonkeyPatch, **env: str) -> None:
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_anthropic_subject_picks_gpt_when_openai_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, ANTHROPIC_API_KEY="x", OPENAI_API_KEY="y")
    assert pick_judge(CLAUDE_SONNET).id == GPT_FLAGSHIP.id


def test_openai_subject_picks_claude_when_anthropic_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, ANTHROPIC_API_KEY="x", OPENAI_API_KEY="y")
    assert pick_judge(GPT_FLAGSHIP).id == CLAUDE_SONNET.id


def test_anthropic_subject_falls_back_to_haiku_with_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Preferred (GPT) key missing, fallback (Haiku) key set — degrade."""
    _set(monkeypatch, ANTHROPIC_API_KEY="x")
    _clear_keys(monkeypatch, "OPENAI_API_KEY")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        judge = pick_judge(CLAUDE_SONNET)
    assert judge.id == CLAUDE_HAIKU.id
    assert any("falling back" in str(rec.message) for rec in w)


def test_openai_subject_no_anthropic_key_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenAI subject's preferred judge is Sonnet and its same-provider
    fallback is also Sonnet — there is no second-line fallback. Without
    ANTHROPIC_API_KEY there's no judge that isn't the subject itself, so
    raise rather than silently let GPT grade GPT."""
    _set(monkeypatch, OPENAI_API_KEY="y")
    _clear_keys(monkeypatch, "ANTHROPIC_API_KEY")
    with pytest.raises(RuntimeError, match="neither"):
        pick_judge(GPT_FLAGSHIP)


def test_neither_key_set_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both preferred and fallback keys missing — fail loud at setup time
    rather than mid-eval inside the scorer."""
    _clear_keys(monkeypatch, "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "TOGETHER_API_KEY")
    with pytest.raises(RuntimeError, match="neither"):
        pick_judge(CLAUDE_SONNET)


def test_open_weights_subject_uses_claude(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set(monkeypatch, ANTHROPIC_API_KEY="x", TOGETHER_API_KEY="z")
    _clear_keys(monkeypatch, "OPENAI_API_KEY")
    assert pick_judge(LLAMA_OPEN).id == CLAUDE_SONNET.id
