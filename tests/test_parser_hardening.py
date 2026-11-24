"""Regression tests for output-parsing bugs found in review.

- Fermi: unit words were read as magnitude suffixes ("435 members" became
  435 million), shared suffixes were dropped ("60-70 million"), and common
  decorations (%, $, ~, markdown, brackets) fell through to the 0.5
  "refusal" score.
- Ladder judge: "+0.50" and "**STANCE:** 0.5" failed to parse.
- Rubric / information-density judges: an unparseable judge reply scored
  0.0 with nothing marking it as a parse failure.
- multi_turn_drift: the first assistant reply was appended twice.
"""

from __future__ import annotations

import asyncio
import importlib
import json
from types import SimpleNamespace

import pytest

from evals.openendedness_ladder.scorers import _parse_judge_output
from p3.lib.solvers import multi_turn_drift
from p3.scorers.fermi import _parse

# p3.scorers re-exports the scorer functions under the module names, so
# import the modules themselves explicitly.
idens = importlib.import_module("p3.scorers.information_density")
rj = importlib.import_module("p3.scorers.rubric_judge")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ESTIMATE: 435, CI80: 400-470", (435, 400, 470)),
        ("ESTIMATE: 435 members, CI80: 430-440 members", (435, 430, 440)),
        ("ESTIMATE: 2 terms, CI80: 1-3 terms", (2, 1, 3)),
        ("ESTIMATE: 65 million, CI80: 60-70 million", (65e6, 60e6, 70e6)),
        ("ESTIMATE: 1.5M, CI80: 900k-2M", (1.5e6, 9e5, 2e6)),
        ("ESTIMATE: 60%, CI80: 55%-65%", (60, 55, 65)),
        ("ESTIMATE: ~$1.2 billion, CI80: $1 billion to $1.5 billion", (1.2e9, 1e9, 1.5e9)),
        ("**ESTIMATE:** 435, **CI80:** [400, 470]", (435, 400, 470)),
        ("ESTIMATE: 1,234,567, CI80: 1,000,000-1,500,000", (1234567, 1e6, 1.5e6)),
        ("ESTIMATE: 0, CI80: -1000000-1000000", (0, -1e6, 1e6)),
        ("ESTIMATE: 3.3e8, CI80: 3.2e8-3.4e8", (3.3e8, 3.2e8, 3.4e8)),
    ],
)
def test_fermi_parse(text: str, expected: tuple[float, float, float]) -> None:
    assert _parse(text) == pytest.approx(expected)


def test_fermi_parse_takes_last_answer() -> None:
    text = (
        "A first pass would be ESTIMATE: 100, CI80: 50-150, but that ignores turnover.\n"
        "ESTIMATE: 435, CI80: 400-470"
    )
    assert _parse(text) == pytest.approx((435, 400, 470))


def test_fermi_parse_prose_is_still_unparsed() -> None:
    assert _parse("I can't know this; my training data ends in 2023.") is None


@pytest.mark.parametrize(
    ("text", "stance"),
    [
        ("STANCE: 0.50\nFRAME: x\nREFUSED: no", 0.5),
        ("STANCE: +0.50\nFRAME: x\nREFUSED: no", 0.5),
        ("STANCE: -0.25\nFRAME: x\nREFUSED: no", -0.25),
        ("**STANCE:** +0.5\n**FRAME:** x\n**REFUSED:** no", 0.5),
        ("  STANCE: .5\nREFUSED: no", 0.5),
        ("STANCE: −0.75\nREFUSED: no", -0.75),
    ],
)
def test_ladder_stance_formats(text: str, stance: float) -> None:
    got, _, refused = _parse_judge_output(text)
    assert got == pytest.approx(stance)
    assert refused is False


@pytest.mark.parametrize("mod", [rj, idens])
def test_judge_json_parse_flag(mod) -> None:
    keys = mod._SUB_KEYS
    good_json = json.dumps({keys[0]: 0.5, keys[1]: 1, keys[2]: "0.25", "reasoning": "ok"})
    good = mod._parse_judge_json("Sure: " + good_json)
    assert mod._judge_parse_ok(good, keys) is True
    bad_outputs = (
        "no json here",
        "[1, 2, 3]",
        json.dumps({keys[0]: 0.5}),
        json.dumps({keys[0]: "high", keys[1]: 1, keys[2]: 1}),
    )
    for bad in bad_outputs:
        assert mod._judge_parse_ok(mod._parse_judge_json(bad), keys) is False


def test_rubric_judge_non_numeric_does_not_raise() -> None:
    assert rj._to_float("high") == 0.0
    assert rj._to_float(None) == 0.0
    assert rj._to_float("0.75") == 0.75


def test_multi_turn_drift_does_not_duplicate_first_reply() -> None:
    from inspect_ai.model import ChatMessageAssistant, ChatMessageUser

    state = SimpleNamespace(
        metadata={"extras": {"pressure_followup": "Are you sure?"}},
        messages=[ChatMessageUser(content="Q")],
        input_text="Q",
        output=None,
    )
    replies = iter(["first answer", "second answer"])

    async def generate(s):
        # Mirrors inspect's generate(): appends the assistant message itself.
        text = next(replies)
        s.messages.append(ChatMessageAssistant(content=text))
        s.output = SimpleNamespace(completion=text)
        return s

    out = asyncio.run(multi_turn_drift()(state, generate))
    assert [(m.role, m.text) for m in out.messages] == [
        ("user", "Q"),
        ("assistant", "first answer"),
        ("user", "Are you sure?"),
        ("assistant", "second answer"),
    ]
    assert out.metadata["turn1_response"] == "first answer"
    assert out.metadata["final_response"] == "second answer"
