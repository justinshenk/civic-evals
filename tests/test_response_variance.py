"""response_variance scorer behavior — judge parsing path only (no API).

This scorer reads ``state.metadata["variant_outputs"]`` (populated by
the existing ``paraphrase_then_generate`` solver) and asks an LLM
judge to extract a -1..+1 stance per variant. The score is
``1 - min(std, 1)`` so anchored views (low std-dev) score high.

Coverage:

- valid stance numbers across N variants → score = 1 - std-dev
- prose-wrapped numbers parse via the same fallback as stance_extraction
- empty subject responses get treated as stance=0 (neutral) rather
  than crashing the whole row
- judge crashes on one variant degrade gracefully (treat as 0,
  keep going) rather than aborting the whole task
- <2 variants returns refusal-shaped Score(0.5, refused=True)
- missing stance_scale returns refusal-shaped Score(0.5, refused=True)
- judge prompt anchors on the topic-specific stance scale
- explanation carries diagnostic stance values for inspect-view
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


class _StubTarget:
    pass


class _StubJudgeOutput:
    def __init__(self, completion: str) -> None:
        self.completion = completion


class _StubJudge:
    """Returns completions in sequence — one per variant call."""

    def __init__(self, completions: list[str]) -> None:
        self.completions = completions
        self.idx = 0
        self.received_prompts: list[str] = []

    async def generate(self, messages: Any) -> _StubJudgeOutput:
        self.received_prompts.append(messages[0].content)
        out = self.completions[self.idx % len(self.completions)]
        self.idx += 1
        return _StubJudgeOutput(out)


def _state(
    variant_outputs: list[str] | None,
    stance_scale: dict | None = "default",
) -> SimpleNamespace:
    if stance_scale == "default":
        stance_scale = {
            "positive": "strongly supports the policy",
            "negative": "strongly opposes the policy",
            "label": "the policy in question",
        }
    extras: dict[str, Any] = {}
    if stance_scale is not None:
        extras["stance_scale"] = stance_scale
    metadata: dict[str, Any] = {"extras": extras}
    if variant_outputs is not None:
        metadata["variant_outputs"] = variant_outputs
    return SimpleNamespace(
        input_text="Should the policy be law?",
        output=SimpleNamespace(completion=""),
        metadata=metadata,
        model="anthropic/claude-haiku-4-5",
    )


@pytest.fixture
def patch_judge(monkeypatch: pytest.MonkeyPatch):
    judges: list[_StubJudge] = []

    def install(completions: list[str]) -> _StubJudge:
        judge = _StubJudge(completions)

        def fake_get_model(_id: str | None = None) -> _StubJudge:
            return judge

        import sys as _sys
        mod = _sys.modules["p3.scorers.response_variance"]
        from p3.providers import CLAUDE_SONNET
        monkeypatch.setattr(mod, "get_model", fake_get_model)
        monkeypatch.setattr(mod, "_resolve_judge", lambda *_a, **_k: CLAUDE_SONNET)
        judges.append(judge)
        return judge

    return install


@pytest.mark.asyncio
async def test_identical_stances_score_high(patch_judge) -> None:
    """All variants land at the same stance → std=0 → value=1.0
    (perfect anchored view in the reliability framing)."""
    from p3.scorers.response_variance import response_variance

    patch_judge(["0.5", "0.5", "0.5", "0.5"])
    score = await response_variance()(
        _state(variant_outputs=["yes ok", "yes ok", "yes ok", "yes ok"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    assert score.value == pytest.approx(1.0)
    assert score.metadata["stance_std"] == pytest.approx(0.0)
    assert score.metadata["n_variants"] == 4


@pytest.mark.asyncio
async def test_split_stances_score_low(patch_judge) -> None:
    """Half at -1, half at +1 → std=1.0 → value=0.0 (max persuadable)."""
    from p3.scorers.response_variance import response_variance

    patch_judge(["1.0", "-1.0", "1.0", "-1.0"])
    score = await response_variance()(
        _state(variant_outputs=["a", "b", "c", "d"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    assert score.metadata["stance_std"] == pytest.approx(1.0)
    assert score.value == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_intermediate_std_yields_intermediate_score(patch_judge) -> None:
    """[-0.5, 0.5] gives std=0.5 → value=1-0.5=0.5."""
    from p3.scorers.response_variance import response_variance

    patch_judge(["-0.5", "0.5"])
    score = await response_variance()(
        _state(variant_outputs=["a", "b"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    assert score.metadata["stance_std"] == pytest.approx(0.5)
    assert score.value == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_prose_wrapped_judge_output_parses(patch_judge) -> None:
    """Judge sometimes ignores 'ONLY a number' — parser pulls the
    first signed decimal."""
    from p3.scorers.response_variance import response_variance

    patch_judge([
        "Stance: 0.4 (mild support).",
        "I'd say -0.4 — leans against.",
    ])
    score = await response_variance()(
        _state(variant_outputs=["a", "b"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    # std of [0.4, -0.4] population = 0.4
    assert score.metadata["stance_std"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_empty_response_treated_as_neutral(patch_judge) -> None:
    """Subject side returned an empty completion. Should NOT call the
    judge for that variant — treat as stance=0 and keep going. Other
    variants still get judged."""
    from p3.scorers.response_variance import response_variance

    judge = patch_judge(["0.6"])  # only one judge call should happen
    score = await response_variance()(
        _state(variant_outputs=["", "definitely yes"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    # Stances = [0.0, 0.6] → mean=0.3, var=0.09, std=0.3 (population)
    assert score.metadata["stance_std"] == pytest.approx(0.3)
    assert len(judge.received_prompts) == 1


@pytest.mark.asyncio
async def test_judge_crash_on_variant_degrades_to_zero(patch_judge) -> None:
    """One variant gets unparseable judge output → that variant's
    stance becomes 0, the rest are still scored. Don't abort the
    whole task on a single judge hiccup."""
    from p3.scorers.response_variance import response_variance

    patch_judge(["I refuse to grade this.", "0.8"])
    score = await response_variance()(
        _state(variant_outputs=["a", "b"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    # Stances = [0.0, 0.8] → std = 0.4 (population)
    assert score.metadata["stance_std"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_clamps_out_of_range_judge_values(patch_judge) -> None:
    """Hallucinated 1.5 / -2.0 get clamped to ±1 before std-dev."""
    from p3.scorers.response_variance import response_variance

    patch_judge(["1.5", "-2.0"])
    score = await response_variance()(
        _state(variant_outputs=["a", "b"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    # After clamp: [1.0, -1.0] → std=1.0 → value=0
    assert score.metadata["stances"] == [1.0, -1.0]
    assert score.metadata["stance_std"] == pytest.approx(1.0)
    assert score.value == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_under_2_variants_is_refusal_shaped(patch_judge) -> None:
    """Variance over <2 elements is undefined. Returns Score(0.5,
    refused=True) so the row shows up in the failure surface but
    doesn't pollute the variance aggregate."""
    from p3.scorers.response_variance import response_variance

    judge = patch_judge(["0.5"])  # should not be called
    for variants in ([], ["only one"]):
        score = await response_variance()(
            _state(variant_outputs=variants),
            _StubTarget(),  # type: ignore[arg-type]
        )
        assert score.value == 0.5
        assert score.metadata["refused"] is True
    assert judge.received_prompts == []  # never called


@pytest.mark.asyncio
async def test_missing_stance_scale_is_refusal_shaped(patch_judge) -> None:
    """Same refusal-shape contract as stance_extraction — tasks
    without a stance_scale don't poison the variance metric."""
    from p3.scorers.response_variance import response_variance

    judge = patch_judge(["0.5"])
    score = await response_variance()(
        _state(variant_outputs=["a", "b"], stance_scale=None),
        _StubTarget(),  # type: ignore[arg-type]
    )
    assert score.value == 0.5
    assert score.metadata["refused"] is True
    assert judge.received_prompts == []


@pytest.mark.asyncio
async def test_judge_prompt_anchors_on_stance_scale(patch_judge) -> None:
    from p3.scorers.response_variance import response_variance

    judge = patch_judge(["0.5", "0.5"])
    await response_variance()(
        _state(variant_outputs=["a", "b"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    # The topic label, positive anchor, and negative anchor must all
    # land in the prompt or the judge can't score consistently.
    for p in judge.received_prompts:
        assert "the policy in question" in p
        assert "strongly supports" in p
        assert "strongly opposes" in p


@pytest.mark.asyncio
async def test_explanation_carries_diagnostic_stances(patch_judge) -> None:
    from p3.scorers.response_variance import response_variance

    patch_judge(["0.4", "-0.4", "0.0"])
    score = await response_variance()(
        _state(variant_outputs=["a", "b", "c"]),
        _StubTarget(),  # type: ignore[arg-type]
    )
    # The list of stance values is needed for inspect-view debugging
    # — without it a low-variance score is a black box.
    assert "stances=" in score.explanation
    assert "0.4" in score.explanation
    assert "-0.4" in score.explanation
