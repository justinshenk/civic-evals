"""Roll up persona_drift_pilot results into per-(topic, axis) drift numbers.

Reads the most recent persona_drift_pilot .eval log (or one passed via
``--log``), pairs baseline ↔ treatment per (topic, axis), and writes
``analysis/persona_drift_pilot_results.json`` with the drift signal each
axis produced.

Drift definition:
- ``persona_attribute`` and ``false_prior``: absolute drift,
  ``|mean_stance(treatment) − mean_stance(baseline)|``.
- ``sycophantic_pressure``: signed drift,
  ``mean_stance(treatment) − mean_stance(baseline)``. Sign matters
  because capitulation is the failure mode, not symmetric movement.

Pilot caveats (write-up only):
- N = 3 epochs per cell is low; stance σ is not meaningfully measurable.
- Many cells score 0.0 because the model holds a hedge stance — that is
  itself the refusal-cliff behavior surfacing again in this eval. The
  pilot's *non-null* signal is concentrated where the model takes a
  stance at all, which on this question set is mostly under
  false-prior conditioning on voter_id.

Usage::

    uv run python analysis/persona_drift_rollup.py
    uv run python analysis/persona_drift_rollup.py --log logs/<file>.eval
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from inspect_ai.log import read_eval_log


REPO = Path(__file__).resolve().parents[1]
OUT_JSON = REPO / "analysis" / "persona_drift_pilot_results.json"


def latest_log() -> Path:
    logs = sorted(
        (REPO / "logs").glob("*_persona-drift-pilot_*.eval"),
        key=lambda p: p.stat().st_mtime,
    )
    if not logs:
        raise SystemExit("No persona_drift_pilot log found under logs/.")
    return logs[-1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", type=Path, default=None)
    args = ap.parse_args()

    log_path = args.log or latest_log()
    print(f"Reading {log_path}", flush=True)
    log = read_eval_log(str(log_path))

    # bucket[(topic, axis, condition)] = [stance, stance, stance]
    bucket: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for s in log.samples:
        extras = (s.metadata or {}).get("extras") or {}
        key = (extras.get("topic"), extras.get("axis"), extras.get("condition"))
        sc = next(iter(s.scores.values()))
        stance = sc.metadata.get("stance")
        if stance is not None:
            bucket[key].append(stance)

    topics = sorted({k[0] for k in bucket if k[0]})
    axes = sorted({k[1] for k in bucket if k[1]})

    cells: dict[str, dict[str, dict[str, dict]]] = {}
    for topic in topics:
        cells[topic] = {}
        for axis in axes:
            base = bucket.get((topic, axis, "baseline"), [])
            treat = bucket.get((topic, axis, "treatment"), [])
            if not base or not treat:
                continue
            mean_b = statistics.fmean(base)
            mean_t = statistics.fmean(treat)
            signed = mean_t - mean_b
            absd = abs(signed)
            cells[topic][axis] = {
                "n_baseline": len(base),
                "n_treatment": len(treat),
                "mean_baseline_stance": round(mean_b, 3),
                "mean_treatment_stance": round(mean_t, 3),
                "drift_signed": round(signed, 3),
                "drift_abs": round(absd, 3),
            }

    # Per-axis aggregate: mean of absolute drift across topics.
    axis_aggregate: dict[str, dict] = {}
    for axis in axes:
        drifts = [
            cells[topic][axis]["drift_abs"]
            for topic in topics
            if axis in cells[topic]
        ]
        signed = [
            cells[topic][axis]["drift_signed"]
            for topic in topics
            if axis in cells[topic]
        ]
        if drifts:
            axis_aggregate[axis] = {
                "n_topics": len(drifts),
                "mean_drift_abs": round(statistics.fmean(drifts), 3),
                "max_drift_abs": round(max(drifts), 3),
                "mean_drift_signed": round(statistics.fmean(signed), 3),
            }

    result = {
        "log": str(log_path.relative_to(REPO)),
        "model": str(log.eval.model),
        "n_samples": len(log.samples),
        "epochs": log.eval.config.epochs,
        "axes": axes,
        "topics": topics,
        "cells": cells,
        "axis_aggregate": axis_aggregate,
        "interpretation": {
            "headline": (
                "Per-axis aggregate drift is small in this pilot because most "
                "cells score stance ≈ 0 (model holds a hedge — the same "
                "refusal-cliff behavior the openendedness ladder measured). "
                "Non-zero drift concentrates in false_prior, and the largest "
                "single cell is voter_id where the model spontaneously refutes "
                "the false premise and flips stance against the policy."
            ),
            "methodology_note": (
                "Stance is a thin signal for false_prior drift specifically: "
                "the model can uncritically fold a false premise into a "
                "both-sides answer and still score stance ≈ 0. A factual-"
                "correctness scorer (did the model accept, refute, or ignore "
                "the false premise) is needed to fully characterize axis 3 "
                "drift. Pilot v2 should add this."
            ),
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2))
    print(f"Wrote {OUT_JSON.relative_to(REPO)}", flush=True)

    # Console summary
    print()
    print("Per-axis aggregate drift (mean |Δstance| across 5 topics):")
    for axis, agg in axis_aggregate.items():
        print(
            f"  {axis:24s}  mean_|Δ|={agg['mean_drift_abs']:+.2f}   "
            f"max_|Δ|={agg['max_drift_abs']:+.2f}   "
            f"mean_signed_Δ={agg['mean_drift_signed']:+.2f}"
        )
    print()
    print("Largest single-cell drifts:")
    flat = [
        (cells[t][a]["drift_abs"], cells[t][a]["drift_signed"], t, a)
        for t in topics for a in axes
        if a in cells[t]
    ]
    flat.sort(reverse=True)
    for absd, signed, t, a in flat[:5]:
        print(f"  {t:18s} × {a:24s}   Δ_signed={signed:+.2f}   |Δ|={absd:+.2f}")


if __name__ == "__main__":
    main()
