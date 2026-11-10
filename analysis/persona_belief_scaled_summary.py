"""Slopes, CIs and swings for persona_belief_scaled rows files. No API calls.

For each rows file: the pooled OLS slope of policy_lean on the persona
ordinal (-2 = left_strong ... +2 = right_strong; negative = the answer
follows the persona), its OLS 95% CI, a 95% CI from resampling whole
questions (answers to the same question are not independent), Pearson r,
and the swing (mean lean for left_strong minus right_strong).

The ``unspecified`` control has no ordinal and is left out of the
regression, as are rows the judge failed to score. Both are counted in
the output.

--compare A B scores two judges on the same answers (matched on persona,
question, rep and answer text): slope under each judge, mean |lean|,
Pearson r, exact agreement and opposite-sign scores.

The question-resampled CI is only reported with 10+ questions: with
fewer, a percentile bootstrap over questions is too narrow to trust.

Usage:
    uv run python analysis/persona_belief_scaled_summary.py ROWS.json [ROWS.json ...]
    uv run python analysis/persona_belief_scaled_summary.py --compare A.json B.json
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy import stats

NAN = float("nan")
MIN_QUESTIONS = 10
REQUIRED = ("persona_key", "persona_ordinal", "question_id", "rep")


def load(path: str | Path) -> list[dict]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError(f"{path}: expected a JSON list of row objects")
    for i, r in enumerate(rows):
        missing = [k for k in REQUIRED if k not in r]
        if missing:
            raise ValueError(f"{path}: row {i} has no {', '.join(missing)}")
    return rows


def _lean(row: dict) -> float | None:
    # Same rule as persona_belief_scaled.parse_judge: a number in -10..10.
    v = (row.get("judge_scores") or {}).get("policy_lean")
    if isinstance(v, bool) or not isinstance(v, int | float):
        return None
    return float(v) if math.isfinite(v) and -10 <= v <= 10 else None


def _slope(xs, ys) -> float:
    xs, ys = np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)
    if len(xs) < 2 or np.ptp(xs) == 0:
        return NAN
    dx = xs - xs.mean()
    return float(dx @ (ys - ys.mean()) / (dx @ dx))


def _label(rows: list[dict], field: str) -> str:
    vals = sorted({str(r[field]) for r in rows if r.get(field) is not None})
    if not vals:
        return "unrecorded"
    partly = any(r.get(field) is None for r in rows)
    return ", ".join(vals) + (" (partly unrecorded)" if partly else "")


def summarize(rows: list[dict], n_boot: int = 4000, seed: int = 0) -> dict:
    _index(rows, "rows")  # a duplicated row would double-count silently
    pts = [(r["question_id"], r["persona_ordinal"], _lean(r)) for r in rows
           if r.get("persona_ordinal") is not None and _lean(r) is not None]
    levels = {o for _, o, _ in pts}
    if len(pts) < 3 or len(levels) < 2:
        raise ValueError(f"{len(pts)} scored rows over {len(levels)} persona level(s); "
                         "need 3+ rows over 2+ levels")
    xs = np.array([o for _, o, _ in pts])
    ys = np.array([y for _, _, y in pts])
    fit = stats.linregress(xs, ys)
    half = stats.t.ppf(0.975, len(pts) - 2) * fit.stderr

    # Resample whole questions: all answers to a question move together.
    by_q = {}
    for q, o, y in pts:
        by_q.setdefault(q, []).append((o, y))
    qs = [by_q[q] for q in sorted(by_q, key=str)]  # sorted: same draws for any row order
    ci_question = (NAN, NAN)
    if len(qs) >= MIN_QUESTIONS:
        rng = np.random.default_rng(seed)
        draws = []
        for _ in range(n_boot):
            sample = [p for i in rng.integers(0, len(qs), len(qs)) for p in qs[i]]
            draws.append(_slope(*zip(*sample, strict=True)))
        if not np.any(np.isnan(draws)):  # a draw with no slope: report no CI
            lo, hi = np.nanpercentile(draws, [2.5, 97.5])
            ci_question = (float(lo), float(hi))

    def mean_for(persona):
        vals = [_lean(r) for r in rows if r.get("persona_key") == persona and _lean(r) is not None]
        return float(np.mean(vals)) if vals else NAN

    return {
        "subject": _label(rows, "subject_model"),
        "judge": _label(rows, "judge_model"),
        "n": len(pts),
        "questions": len(qs),
        "reps": len({r.get("rep") for r in rows}),
        "slope": float(fit.slope),
        "ci_ols": (float(fit.slope - half), float(fit.slope + half)),
        "ci_question": ci_question,
        "r": float(fit.rvalue),
        "swing": mean_for("left_strong") - mean_for("right_strong"),
        "control_excluded": sum(r.get("persona_ordinal") is None for r in rows),
        "unscored": sum(r.get("persona_ordinal") is not None and _lean(r) is None for r in rows),
    }


def _key(r: dict) -> tuple:
    return (r.get("persona_key"), r.get("question_id"), r.get("rep"), r.get("response_text"))


def _index(rows: list[dict], name: str) -> dict:
    out = {}
    for r in rows:
        if _key(r) in out:
            raise ValueError(f"{name}: two rows share persona/question/rep/answer {_key(r)[:3]}")
        out[_key(r)] = r
    return out


def compare(a_rows: list[dict], b_rows: list[dict]) -> dict:
    a, b = _index(a_rows, "A"), _index(b_rows, "B")
    both = [(a[k], b[k]) for k in a if k in b]
    scored = [(x, y) for x, y in both if _lean(x) is not None and _lean(y) is not None]
    la = np.array([_lean(x) for x, _ in scored])
    lb = np.array([_lean(y) for _, y in scored])
    belief = [(x["persona_ordinal"], _lean(x), _lean(y)) for x, y in scored
              if x.get("persona_ordinal") is not None]
    sa = _slope([o for o, _, _ in belief], [v for _, v, _ in belief]) if belief else NAN
    sb = _slope([o for o, _, _ in belief], [v for _, _, v in belief]) if belief else NAN
    r = NAN
    if len(scored) >= 2 and np.ptp(la) > 0 and np.ptp(lb) > 0:
        r = float(np.corrcoef(la, lb)[0, 1])
    abs_a = float(np.abs(la).mean()) if scored else NAN
    abs_b = float(np.abs(lb).mean()) if scored else NAN
    return {
        "matched": len(both), "only_a": len(a) - len(both), "only_b": len(b) - len(both),
        "scored": len(scored), "belief_bearing": len(belief),
        "slope_a": sa, "slope_b": sb, "slope_ratio": sb / sa if sa else NAN,
        "abs_a": abs_a, "abs_b": abs_b, "abs_ratio": abs_b / abs_a if abs_a else NAN,
        "r": r, "exact": int((la == lb).sum()), "sign_disagree": int((la * lb < 0).sum()),
        "judge_a": _label(a_rows, "judge_model"), "judge_b": _label(b_rows, "judge_model"),
    }


def _ci(ci: tuple[float, float]) -> str:
    return "n/a" if any(np.isnan(ci)) else f"[{ci[0]:+.2f}, {ci[1]:+.2f}]"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*", metavar="ROWS_JSON", help="rows files to summarise")
    ap.add_argument("--compare", nargs=2, metavar=("A_JSON", "B_JSON"),
                    help="compare two judges' scores on the same answers")
    ap.add_argument("--n-boot", type=int, default=4000, help="question-resampling draws")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    if not args.files and not args.compare:
        ap.error("give one or more rows files, or --compare A B")
    if args.n_boot < 1000:
        ap.error("--n-boot must be at least 1000 for a 95% percentile interval")
    paths = [*args.files, *(args.compare or [])]
    for p in paths:
        if not Path(p).is_file():
            ap.error(f"no such file: {p}")
    try:
        loaded = {p: load(p) for p in paths}
    except ValueError as e:
        ap.error(str(e))

    if args.files:
        print("| subject | judge | questions x reps | n | slope | 95% CI (OLS) "
              "| 95% CI (questions resampled) | r | swing |")
        print("|---|---|---|---|---|---|---|---|---|")
        notes = []
        for p in args.files:
            rows = loaded[p]
            try:
                s = summarize(rows, args.n_boot, args.seed)
            except ValueError as e:
                notes.append(f"- {p}: skipped, {e}")
                continue
            subject = Path(p).stem if s["subject"] == "unrecorded" else s["subject"]
            print(f"| {subject} | {s['judge']} | {s['questions']} x {s['reps']} | {s['n']} "
                  f"| {s['slope']:+.2f} | {_ci(s['ci_ols'])} | {_ci(s['ci_question'])} "
                  f"| {s['r']:+.2f} | {s['swing']:.2f} |")
            notes.append(f"- {Path(p).name}: {s['control_excluded']} `unspecified` control rows "
                         f"and {s['unscored']} unscored rows left out of the regression")
        print(f"\nn = scored rows with a persona ordinal. Question-resampled CI: "
              f"{args.n_boot} draws, seed {args.seed}; n/a under {MIN_QUESTIONS} questions. "
              "It can be narrower than the OLS CI: every question covers every persona, "
              "so per-question offsets widen OLS but not the resampled CI.")
        print("\n".join(notes))

    if args.compare:
        a, b = args.compare
        try:
            c = compare(loaded[a], loaded[b])
        except ValueError as e:
            ap.error(str(e))
        print(f"\nJudge comparison on identical answers\n  A: {a} (judge {c['judge_a']})"
              f"\n  B: {b} (judge {c['judge_b']})")
        print(f"  matched answers: {c['matched']} (only in A: {c['only_a']}, "
              f"only in B: {c['only_b']}); scored by both: {c['scored']}")
        print(f"  slope over {c['belief_bearing']} belief-bearing answers: "
              f"A {c['slope_a']:+.3f}, B {c['slope_b']:+.3f}, B/A = {c['slope_ratio']:.3f}")
        print(f"  mean |lean|: A {c['abs_a']:.2f}, B {c['abs_b']:.2f}, B/A = {c['abs_ratio']:.3f}")
        print(f"  Pearson r = {c['r']:.3f}; same score {c['exact']}/{c['scored']}; "
              f"opposite sign {c['sign_disagree']}/{c['scored']}")


if __name__ == "__main__":
    main()
