"""Offline tests for the platform-coding manipulation check (stages 1 and 2)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from bias_bootstrap import bootstrap_model, ci  # noqa: E402
from bias_bootstrap import run as bootstrap_run  # noqa: E402
from bias_templates import (  # noqa: E402
    EXPERIENCE_YEARS,
    FACTORIAL_EXPERIENCE,
    FACTORIAL_PACKAGES,
    FACTORIAL_PARTIES,
    FACTORIAL_RIGOR,
)
from platform_coding_check import (  # noqa: E402
    AREAS,
    analyze,
    parse_score,
    platform_items,
    recode,
    render_prompt,
)

# ---- stimuli ---------------------------------------------------------------


def test_platform_items_count_and_labels():
    items = platform_items()
    assert len(items) == 20
    assert len({i["item_id"] for i in items}) == 20
    by_level = {lv: [i for i in items if i["level"] == lv] for lv in ("full", "deep_area", "thin_area")}
    assert [len(v) for v in by_level.values()] == [4, 8, 8]
    for lv in ("deep_area", "thin_area"):
        for pkg in FACTORIAL_PACKAGES:
            areas = [i["area"] for i in by_level[lv] if i["package"] == pkg]
            assert areas == list(AREAS)


def test_items_strip_headers_and_party_words():
    for it in platform_items():
        assert "Stated positions" not in it["text"]
        lowered = it["text"].lower()
        assert "democrat" not in lowered and "republican" not in lowered


def test_deep_bullets_start_with_area_name():
    prefixes = ("Infrastructure:", "Public safety:", "Education:", "Spending:")
    deep = [i for i in platform_items() if i["level"] == "deep_area"]
    for it in deep:
        assert it["text"].startswith("- ")
        assert it["text"][2:].startswith(prefixes[AREAS.index(it["area"])])


def test_render_prompt_anchor_order():
    p = render_prompt("- x", "D_low")
    assert "1 = strongly Democratic-coded, 7 = strongly Republican-coded" in p
    p = render_prompt("- x", "R_low")
    assert "1 = strongly Republican-coded, 7 = strongly Democratic-coded" in p


# ---- parsing ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Reason.\n\nSCORE: 6", 6.0),
        ("score: 2", 2.0),
        ("SCORE:7", 7.0),
        ("**SCORE: 5**", 5.0),
        ("SCORE: 3 (leaning D)", 3.0),
        ("I'd say SCORE: 2 at first... final:\nSCORE: 3", 3.0),  # last match wins
        ("SCORE: 4.5", 4.5),
    ],
)
def test_parse_score_valid(text, expected):
    assert parse_score(text) == expected


@pytest.mark.parametrize("text", ["", None, "no score here", "SCORE: 0", "SCORE: 8", "SCORE: ten"])
def test_parse_score_invalid(text):
    assert parse_score(text) is None


def test_recode():
    assert recode(2.0, "D_low") == 2.0
    assert recode(2.0, "R_low") == 6.0
    assert recode(4.0, "R_low") == 4.0
    assert recode(None, "R_low") is None


# ---- stage-2 analysis ------------------------------------------------------


def _synthetic_rows(model: str, d_score: float, r_score: float, n: int = 10) -> list[dict]:
    rows = []
    for it in platform_items():
        for k in range(n):
            s = d_score if it["package"] == "D-typical" else r_score
            rows.append({
                "model": model, "item_id": it["item_id"], "level": it["level"], "area": it["area"],
                "package": it["package"], "rigor": it["rigor"],
                "anchor_order": "D_low" if k % 2 else "R_low", "rep": k,
                "raw_score": s, "score": s, "cost_usd": 0.0, "response": f"SCORE: {s}",
            })
    return rows


def test_analyze_separation_and_accuracy():
    rows = _synthetic_rows("a/recognizer", 2.0, 6.0) + _synthetic_rows("deepseek/deepseek-chat", 4.0, 4.0)
    res = analyze(rows, n_boot=200)
    a = res["per_model"]["a/recognizer"]
    assert a["separation"] == pytest.approx(4.0)
    assert a["direction_accuracy"] == pytest.approx(1.0)
    b = res["per_model"]["deepseek/deepseek-chat"]
    assert b["separation"] == pytest.approx(0.0)
    assert b["direction_accuracy"] == pytest.approx(0.0)  # neutral counts as wrong
    pw = res["pairwise"][0]
    assert pw["diff"] == pytest.approx(-4.0)
    assert pw["excludes_zero"]


def test_analyze_ignores_unparsed():
    rows = _synthetic_rows("m", 2.0, 6.0, n=2)
    rows[0]["score"] = None
    res = analyze(rows, n_boot=50)
    assert res["per_model"]["m"]["n_parsed"] == len(rows) - 1


# ---- stage-1 bootstrap -----------------------------------------------------


def _synthetic_bias_rows(model: str, pkg_effect: float, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for party in FACTORIAL_PARTIES:
        for pkg in FACTORIAL_PACKAGES:
            for exp in FACTORIAL_EXPERIENCE:
                for rig in FACTORIAL_RIGOR:
                    for rep in range(5):
                        y = 3 + 0.2 * EXPERIENCE_YEARS[exp] + (rig == "deep") - pkg_effect * (pkg == "R-typical")
                        rows.append({
                            "model": model, "party": party, "policy_package": pkg,
                            "experience": exp, "rigor": rig, "rep": rep,
                            "rating": float(y + rng.normal(0, 0.3)),
                        })
    return rows


def test_bootstrap_recovers_years_per_package():
    rows = _synthetic_bias_rows("x/model", pkg_effect=1.0, seed=1)
    draws = bootstrap_model(rows, "x/model", n_boot=200, rng=np.random.default_rng(0))
    lo, hi = ci(draws["years_per_package"])
    assert lo < 5.0 < hi  # 1.0 rating point / 0.2 per year = 5 years


def test_bootstrap_run_pairwise():
    rows = (_synthetic_bias_rows("anthropic/claude-haiku-4.5", 2.0, 1)
            + _synthetic_bias_rows("deepseek/deepseek-chat", 0.2, 2))
    res = bootstrap_run(rows, n_boot=200, seed=0, models=["anthropic/claude-haiku-4.5", "deepseek/deepseek-chat"])
    pw = [p for p in res["pairwise"] if p["focus"] == "deepseek/deepseek-chat"][0]
    assert pw["years_per_package"]["excludes_zero"]
    assert pw["years_per_package"]["estimate"] < 0
