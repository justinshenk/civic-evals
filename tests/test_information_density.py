"""Information-density scorer behavior — judge parsing path only (no API).

Patches ``inspect_ai.model.get_model`` so the scorer talks to a stub
judge instead of a real provider. We test:

- valid JSON from the judge maps cleanly into sub_scores and a mean value
- judges that wrap their JSON in prose still parse via the regex fallback
- garbage from the judge falls back to a zero score rather than crashing
- out-of-range floats and string scores get clipped, not exploded
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest


class _StubTarget:
    pass


class _StubJudgeOutput:
    def __init__(self, completion: str) -> None:
        self.completion = completion


class _StubJudge:
    """Records the prompt it was called with and returns a fixed completion."""

    def __init__(self, completion: str) -> None:
        self.completion = completion
        self.received_prompt: str | None = None

    async def generate(self, messages: Any) -> _StubJudgeOutput:
        # messages is [ChatMessageUser(content=...)]; capture the user content.
        self.received_prompt = messages[0].content
        return _StubJudgeOutput(self.completion)


def _state(input_text: str = "How does this policy affect me?", completion: str = "It depends.") -> SimpleNamespace:
    return SimpleNamespace(
        input_text=input_text,
        output=SimpleNamespace(completion=completion),
        metadata={"persona": {"role": "first_time_voter", "urgency": "high"}},
        model="anthropic/claude-haiku-4-5",
    )


@pytest.fixture
def patch_judge(monkeypatch: pytest.MonkeyPatch):
    """Returns a setter that swaps the judge model out for a stub."""
    judges: list[_StubJudge] = []

    def install(completion: str) -> _StubJudge:
        judge = _StubJudge(completion)

        def fake_get_model(_id: str | None = None) -> _StubJudge:
            return judge

        # ``p3.scorers.__init__`` re-exports the ``information_density``
        # function under the package name, shadowing the submodule on the
        # parent. Reach the module object through ``sys.modules`` so we
        # patch the actual ``get_model`` reference the scorer will use.
        import sys as _sys
        mod = _sys.modules["p3.scorers.information_density"]
        from p3.providers import CLAUDE_SONNET
        monkeypatch.setattr(mod, "get_model", fake_get_model)
        monkeypatch.setattr(mod, "_resolve_judge", lambda *_a, **_k: CLAUDE_SONNET)
        judges.append(judge)
        return judge

    return install


@pytest.mark.asyncio
async def test_parses_valid_json(patch_judge) -> None:
    from p3.scorers.information_density import information_density

    patch_judge(json.dumps({
        "actionability": 0.8,
        "specificity_calibration": 0.6,
        "persuasion_pressure": 0.9,
        "reasoning": "concrete deadline given; neutral framing.",
    }))
    score = await information_density()(_state(), _StubTarget())  # type: ignore[arg-type]

    assert score.value == pytest.approx((0.8 + 0.6 + 0.9) / 3)
    assert score.metadata["sub_scores"] == {
        "actionability": 0.8,
        "specificity_calibration": 0.6,
        "persuasion_pressure": 0.9,
    }
    assert "deadline" in score.explanation


@pytest.mark.asyncio
async def test_extracts_json_from_prose_wrapped_judge(patch_judge) -> None:
    from p3.scorers.information_density import information_density

    patch_judge(
        "Here is my grade:\n"
        '{"actionability": 0.5, "specificity_calibration": 0.5, '
        '"persuasion_pressure": 1.0, "reasoning": "fine"}\n'
        "Hope this helps."
    )
    score = await information_density()(_state(), _StubTarget())  # type: ignore[arg-type]
    assert score.value == pytest.approx((0.5 + 0.5 + 1.0) / 3)


@pytest.mark.asyncio
async def test_garbage_judge_output_returns_zero(patch_judge) -> None:
    from p3.scorers.information_density import information_density

    patch_judge("I refuse to grade this.")
    score = await information_density()(_state(), _StubTarget())  # type: ignore[arg-type]
    # All three sub_scores default to 0 → mean is 0, no crash.
    assert score.value == 0.0
    assert score.metadata["sub_scores"] == {
        "actionability": 0.0,
        "specificity_calibration": 0.0,
        "persuasion_pressure": 0.0,
    }


@pytest.mark.asyncio
async def test_clips_out_of_range_and_strings(patch_judge) -> None:
    from p3.scorers.information_density import information_density

    patch_judge(json.dumps({
        "actionability": 1.5,           # over 1 → clipped to 1
        "specificity_calibration": -0.3,  # negative → clipped to 0
        "persuasion_pressure": "0.7",    # string → coerced
        "reasoning": "edge cases",
    }))
    score = await information_density()(_state(), _StubTarget())  # type: ignore[arg-type]
    sub = score.metadata["sub_scores"]
    assert sub["actionability"] == 1.0
    assert sub["specificity_calibration"] == 0.0
    assert sub["persuasion_pressure"] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_persona_threaded_into_judge_prompt(patch_judge) -> None:
    from p3.scorers.information_density import information_density

    judge = patch_judge(json.dumps({
        "actionability": 0.5, "specificity_calibration": 0.5,
        "persuasion_pressure": 0.5, "reasoning": "ok",
    }))
    await information_density()(_state(), _StubTarget())  # type: ignore[arg-type]
    assert judge.received_prompt is not None
    # Persona dict should appear in the prompt so the judge can score
    # actionability against the asker's attributes (urgency=high should
    # weigh the rubric's preference for action-focused framing).
    assert "first_time_voter" in judge.received_prompt
    assert "urgency" in judge.received_prompt
