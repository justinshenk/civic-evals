"""Offline checks for ``analysis/persona_belief_scaled_summary.py``.

Synthetic rows pin the statistics; the saved rows files pin the numbers
reported in PR #35 and the baseline write-up.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

import analysis.persona_belief_scaled_summary as summ

ORD = {"left_strong": -2.0, "left_mild": -1.0, "moderate": 0.0,
       "right_mild": 1.0, "right_strong": 2.0, "unspecified": None}
ANALYSIS = Path(__file__).resolve().parent.parent / "analysis"
Q10 = tuple(f"q{i}" for i in range(10))


def _row(persona, q, lean, rep=0, text=None):
    return {
        "persona_key": persona, "persona_ordinal": ORD[persona], "question_id": q,
        "rep": rep, "response_text": text or f"{persona}/{q}/{rep}",
        "judge_scores": None if lean is None else {"policy_lean": lean},
    }


def _grid(lean_fn, questions=("q1", "q2", "q3", "q4"), reps=(0,)):
    """Every persona x question x rep, lean = lean_fn(ordinal, question index)."""
    return [_row(p, q, lean_fn(o, i), rep)
            for i, q in enumerate(questions) for rep in reps
            for p, o in ORD.items() if o is not None]


def test_slope_is_recovered_and_question_ci_collapses_when_every_question_agrees():
    # Same slope (-2) on every question, different offsets: resampling
    # questions can't move a balanced pooled slope, so the CI is a point.
    s = summ.summarize(_grid(lambda o, i: i % 4 - 2 * o, questions=Q10))  # leans stay in -10..10
    assert s["slope"] == pytest.approx(-2.0)
    assert s["ci_question"] == pytest.approx((-2.0, -2.0))
    assert s["ci_ols"][0] < -2.0 < s["ci_ols"][1]  # offsets are unmodelled noise to OLS
    assert s["n"] == 50 and s["questions"] == 10 and s["reps"] == 1


def test_control_and_unscored_rows_are_excluded_and_counted():
    rows = _grid(lambda o, i: -o)
    base = summ.summarize(rows)
    extra = [_row("unspecified", "q1", 10), _row("unspecified", "q2", -10),
             _row("unspecified", "q3", None),  # unscored control: still a control row
             _row("left_strong", "q1", None, rep=1), _row("right_strong", "q2", None, rep=1)]
    s = summ.summarize(rows + extra)
    assert s["slope"] == pytest.approx(base["slope"]) and s["n"] == base["n"]
    assert s["control_excluded"] == 3 and s["unscored"] == 2


def test_ols_ci_is_the_two_sided_95_percent_t_interval():
    import numpy as np
    from scipy import stats
    rows = _grid(lambda o, i: (-o * (i + 2)) % 9 - 4, questions=tuple(f"q{i}" for i in range(6)))
    x = np.array([r["persona_ordinal"] for r in rows])
    y = np.array([r["judge_scores"]["policy_lean"] for r in rows], dtype=float)
    b = ((x - x.mean()) @ (y - y.mean())) / ((x - x.mean()) @ (x - x.mean()))
    resid = y - y.mean() - b * (x - x.mean())
    se = np.sqrt(resid @ resid / (len(x) - 2) / ((x - x.mean()) @ (x - x.mean())))
    half = stats.t.ppf(0.975, len(x) - 2) * se
    assert summ.summarize(rows)["ci_ols"] == pytest.approx((b - half, b + half))


def test_swing_is_left_strong_mean_minus_right_strong_mean():
    rows = [_row("left_strong", "q1", 6), _row("left_strong", "q2", 2),
            _row("right_strong", "q1", -3), _row("right_strong", "q2", -1),
            _row("moderate", "q1", 0)]
    assert summ.summarize(rows)["swing"] == pytest.approx(4 - (-2))


@pytest.mark.parametrize("rows", [
    [],
    [_row("moderate", "q1", 1), _row("moderate", "q2", 2), _row("moderate", "q3", 0)],
    [_row("unspecified", "q1", 1), _row("left_strong", "q1", None)],
])
def test_too_little_data_raises_a_clear_error(rows):
    with pytest.raises(ValueError, match="persona level"):
        summ.summarize(rows)


@pytest.mark.parametrize("k", [1, 5, 9])
def test_under_ten_questions_gives_no_question_ci_instead_of_a_too_narrow_one(k):
    s = summ.summarize(_grid(lambda o, i: (-o * (i + 2)) % 9 - 4, questions=Q10[:k]))
    assert all(math.isnan(x) for x in s["ci_question"])


def test_bootstrap_is_reproducible_for_a_seed():
    rows = _grid(lambda o, i: (-o * (i + 1)) % 7 - 3, questions=Q10)
    ci = summ.summarize(rows, seed=3)["ci_question"]
    assert not any(math.isnan(x) for x in ci) and ci == summ.summarize(rows, seed=3)["ci_question"]


@pytest.mark.parametrize("lean", [True, None, "4", float("nan"), float("inf"), 11, -10.5])
def test_lean_that_parse_judge_would_reject_counts_as_unscored(lean):
    rows = _grid(lambda o, i: -o)
    bad = _row("left_strong", "q9", 1)
    bad["judge_scores"] = {"policy_lean": lean} if lean is not None else {"rationale": "x"}
    s = summ.summarize(rows + [bad])
    assert s["n"] == 20 and s["unscored"] == 1 and not math.isnan(s["slope"])


def test_duplicated_rows_are_rejected_not_double_counted():
    rows = _grid(lambda o, i: -o)
    with pytest.raises(ValueError, match="share"):
        summ.summarize(rows + rows[:1])


def test_partly_recorded_model_fields_are_labelled_not_printed_as_none():
    rows = _grid(lambda o, i: -o)
    rows[0]["judge_model"] = "a/judge"
    assert summ.summarize(rows)["judge"] == "a/judge (partly unrecorded)"
    assert summ.summarize(_grid(lambda o, i: -o))["judge"] == "unrecorded"


# --- judge comparison -------------------------------------------------------

def test_compare_identical_files_agrees_perfectly():
    rows = _grid(lambda o, i: -2 * o + i)
    c = summ.compare(rows, rows)
    assert c["matched"] == 20 and c["exact"] == 20 and c["sign_disagree"] == 0
    assert c["r"] == pytest.approx(1.0) and c["slope_ratio"] == pytest.approx(1.0)


def test_compare_reports_a_softer_judge_and_skips_unmatched_answers():
    a = _grid(lambda o, i: -4 * o)
    b = [dict(r, judge_scores={"policy_lean": r["judge_scores"]["policy_lean"] // 2}) for r in a]
    b[0] = dict(b[0], response_text="a different answer")  # not the same answer -> unmatched
    b.append(_row("moderate", "q99", 5))  # only in b
    c = summ.compare(a, b)
    assert c["matched"] == 19 and c["only_a"] == 1 and c["only_b"] == 2
    assert c["slope_b"] / c["slope_a"] == pytest.approx(0.5) == c["slope_ratio"]
    assert c["abs_ratio"] == pytest.approx(0.5)


def test_compare_does_not_pair_different_reps_with_the_same_text():
    a = [_row("left_strong", "q1", 4, rep=0, text="same"), _row("left_strong", "q1", -4, rep=1, text="same")]
    b = [_row("left_strong", "q1", 4, rep=1, text="same"), _row("left_strong", "q1", -4, rep=0, text="same")]
    c = summ.compare(a, b)
    assert c["matched"] == 2 and c["exact"] == 0 and c["sign_disagree"] == 2


# --- CLI --------------------------------------------------------------------

def test_cli_prints_a_markdown_row_per_file(tmp_path, capsys):
    p = tmp_path / "rows.json"
    p.write_text(json.dumps(_grid(lambda o, i: -o)))
    summ.main([str(p), str(p)])
    out = capsys.readouterr().out
    assert out.count("| rows | unrecorded | 4 x 1 | 20 | -1.00 |") == 2
    assert out.count("[+nan") == 0 and "| n/a |" in out  # 4 questions: no resampled CI


@pytest.mark.parametrize("argv", [[], ["--compare", "only_one.json"], ["missing.json"]])
def test_cli_misuse_exits(argv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        summ.main(argv)


# --- the saved files reproduce the reported numbers -------------------------

@pytest.mark.parametrize("name, n, slope", [
    ("persona_belief_scaled_rows.json", 225, -2.318),
    ("persona_belief_scaled_rows__anthropic_claude-haiku-5.5__judge-anthropic_claude-sonnet-4.6__anthropic__q15r1.json", 75, -1.720),
    ("persona_belief_scaled_rows__anthropic_claude-sonnet-5.5__judge-anthropic_claude-sonnet-4.6__anthropic__q15r1.json", 75, -1.120),
    ("persona_belief_scaled_rows__anthropic_claude-opus-5.5__judge-anthropic_claude-sonnet-4.6__anthropic__q15r1.json", 75, -1.313),
])
def test_saved_rows_reproduce_reported_slopes(name, n, slope):
    s = summ.summarize(summ.load(ANALYSIS / name))
    assert s["n"] == n and s["slope"] == pytest.approx(slope, abs=5e-4)
    assert s["control_excluded"] == s["n"] // 5
    assert s["ci_question"][0] < s["slope"] < s["ci_question"][1] < 0


# --- invariants -------------------------------------------------------------

def test_summary_does_not_depend_on_row_order():
    import random
    rows = _grid(lambda o, i: (-o * (i + 2)) % 9 - 4, questions=Q10)
    shuffled = rows[:]
    random.Random(1).shuffle(shuffled)
    a, b = summ.summarize(shuffled), summ.summarize(rows)
    assert a.keys() == b.keys()
    for k in a:  # equal up to float summation order
        assert a[k] == (pytest.approx(b[k]) if not isinstance(b[k], str) else b[k]), k


def test_scaling_leans_scales_slope_and_both_cis():
    rows = _grid(lambda o, i: (-o * (i + 2)) % 9 - 4, questions=Q10)
    # leans stay within -10..10 after tripling (raw leans are -4..4 -> -12..12 would not)
    rows = [dict(r, judge_scores={"policy_lean": max(-3, min(3, r["judge_scores"]["policy_lean"]))})
            for r in rows]
    tripled = [dict(r, judge_scores={"policy_lean": 3 * r["judge_scores"]["policy_lean"]}) for r in rows]
    s, t = summ.summarize(rows), summ.summarize(tripled)
    assert t["slope"] == pytest.approx(3 * s["slope"])
    assert t["ci_ols"] == pytest.approx(tuple(3 * x for x in s["ci_ols"]))
    assert t["ci_question"] == pytest.approx(tuple(3 * x for x in s["ci_question"]))
    assert t["r"] == pytest.approx(s["r"])


def test_compare_is_symmetric():
    a = _grid(lambda o, i: -3 * o + i)
    b = [dict(r, judge_scores={"policy_lean": r["judge_scores"]["policy_lean"] - (i % 3)})
         for i, r in enumerate(a)]
    ab, ba = summ.compare(a, b), summ.compare(b, a)
    assert ab["slope_ratio"] * ba["slope_ratio"] == pytest.approx(1.0)
    assert ab["abs_ratio"] * ba["abs_ratio"] == pytest.approx(1.0)
    for k in ("matched", "scored", "r", "exact", "sign_disagree"):
        assert ab[k] == pytest.approx(ba[k])


# --- more CLI misuse --------------------------------------------------------

def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj))
    return str(p)


def test_cli_rejects_bad_n_boot_non_list_file_and_duplicate_answers(tmp_path):
    good = _write(tmp_path, "good.json", _grid(lambda o, i: -o))
    obj = _write(tmp_path, "obj.json", {"rows": []})
    dup = _write(tmp_path, "dup.json", _grid(lambda o, i: -o) * 2)
    no_q = _write(tmp_path, "no_q.json", [{k: v for k, v in r.items() if k != "question_id"}
                                          for r in _grid(lambda o, i: -o)])
    for argv in (["--n-boot", "0", good], ["--n-boot", "999", good], [obj], [no_q],
                 ["--compare", good, dup]):
        with pytest.raises(SystemExit):
            summ.main(argv)


def test_cli_files_and_compare_together(tmp_path, capsys):
    good = _write(tmp_path, "good.json", _grid(lambda o, i: -o))
    summ.main([good, "--compare", good, good])
    out = capsys.readouterr().out
    assert "| good |" in out and "same score 20/20" in out


def test_cli_compare_reports_unmatched_answers(tmp_path, capsys):
    a = _grid(lambda o, i: -o)
    b = a[1:] + [_row("moderate", "q99", 3)]
    summ.main(["--compare", _write(tmp_path, "a.json", a), _write(tmp_path, "b.json", b)])
    out = capsys.readouterr().out
    assert "matched answers: 19 (only in A: 1, only in B: 1); scored by both: 19" in out


def test_cli_skips_a_file_with_too_little_data_and_keeps_going(tmp_path, capsys):
    good = _write(tmp_path, "good.json", _grid(lambda o, i: -o))
    thin = _write(tmp_path, "thin.json", [_row("moderate", "q1", 1)])
    summ.main([thin, good])
    out = capsys.readouterr().out
    assert "thin.json: skipped" in out and "| good |" in out


def test_resamples_without_a_slope_give_no_ci_rather_than_a_partial_one():
    # 9 questions answered only by the moderate persona: many resamples
    # contain no persona spread, so their slope is undefined.
    rows = [_row("moderate", q, 0) for q in Q10[:9]] + _grid(lambda o, i: -o, questions=("q9",))
    s = summ.summarize(rows)
    assert s["questions"] == 10 and all(math.isnan(x) for x in s["ci_question"])


def test_mixed_int_and_str_question_ids_do_not_crash():
    rows = _grid(lambda o, i: (-o * (i + 2)) % 9 - 4, questions=Q10)
    for r in rows:
        if r["question_id"] == "q3":
            r["question_id"] = 3
    assert summ.summarize(rows)["questions"] == 10
