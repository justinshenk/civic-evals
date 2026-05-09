"""Generate the openendedness-variance figure from openendedness_ladder logs.

v2 design (no L/R framing). The metric pool is N=10 epochs per (topic,
rung, model) cell, and three signals are extracted per response by
``multi_signal_extraction``: stance ∈ [−1,+1], frame label, refusal flag.

The figure has three panels — one per signal — plus an optional fourth
panel showing the judge-rated-openendedness scatter (validation):

- **Panel 1**: σ(stance) vs. rung. One line per model.
- **Panel 2**: Shannon H over the frame distribution vs. rung.
- **Panel 3**: refusal rate vs. rung.
- **Panel 4** (optional, if the openendedness sidecar exists):
  σ(stance) vs. judge-rated openendedness, scatter colored by model.

Pre-registered hypothesis: each of σ, H, and refusal-rate grow
monotonically with rung. r1 should converge across all three (low
variance, frame=factual_answer dominates → low entropy, ~0% refusal);
r5 should disperse across all three.

Usage::

    uv run python analysis/score_openendedness.py    # one-time, populates sidecar
    uv run python analysis/openendedness_figure.py logs/ \
        --out evals/openendedness_ladder/figure.png

The script also prints markdown summary tables of each signal for
paste-into-PR consumption.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display
import matplotlib.pyplot as plt  # noqa: E402
from inspect_ai.log import list_eval_logs, read_eval_log  # noqa: E402

EVAL_NAME = "openendedness_ladder"
SIDECAR_PATH = Path("evals/openendedness_ladder/openendedness_scores.json")


def collect(log_dir: Path) -> list[dict[str, Any]]:
    """Return one row per (model, topic, rung, epoch) cell.

    Reads stance / frame / refused from the multi_signal_extraction
    scorer's metadata. Skips rows without a stance number (counts them
    as refusal-shaped, but the figure draws explicit refusal rate so
    we don't double-count).
    """
    rows: list[dict[str, Any]] = []
    scorer_keys = ("multi_signal_extraction", "stance_extraction")
    for log_file in list_eval_logs(str(log_dir)):
        log = read_eval_log(log_file)
        if log.eval.task != EVAL_NAME:
            continue
        model = getattr(log.eval, "model", "") or "unknown"
        for sample in log.samples or []:
            scores = sample.scores or {}
            score = next(
                (scores[k] for k in scorer_keys if k in scores),
                None,
            )
            if score is None:
                continue
            sm = score.metadata or {}
            extras = (sample.metadata or {}).get("extras") or sm
            rows.append(
                {
                    "model": model,
                    "topic": extras.get("topic") or sm.get("topic"),
                    "rung": int(extras.get("rung") or sm.get("rung") or 0),
                    "epoch": getattr(sample, "epoch", None),
                    "stance": sm.get("stance"),  # may be None on refusal/parse-fail
                    "frame": sm.get("frame"),
                    "refused": bool(sm.get("refused")),
                }
            )
    return rows


def stance_sigma(rows: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    """model → rung → mean σ(stance) across topics.

    Per (model, topic, rung) we compute σ over epochs (population
    std-dev so single-sample cells go to 0 deterministically), then
    average across topics. Cells with fewer than 2 valid stance
    samples contribute 0 to the average (collapsing the variance
    estimate to 0 rather than dropping the cell).
    """
    by_cell: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for r in rows:
        if r["stance"] is None:
            continue
        by_cell[(r["model"], r["topic"], r["rung"])].append(float(r["stance"]))

    nest: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for (model, _topic, rung), stances in by_cell.items():
        if len(stances) >= 2:
            nest[model][rung].append(statistics.pstdev(stances))
        else:
            nest[model][rung].append(0.0)

    return {
        model: {rung: sum(sigmas) / len(sigmas) for rung, sigmas in by_rung.items()}
        for model, by_rung in nest.items()
    }


def frame_entropy(rows: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    """model → rung → mean Shannon H over frame distribution across topics.

    Per (model, topic, rung) compute Shannon entropy (in bits) over the
    empirical frame distribution across epochs. Cells with no valid
    frame labels contribute 0. Average across topics for the rung-level
    estimate.
    """
    by_cell: dict[tuple[str, str, int], Counter] = defaultdict(Counter)
    for r in rows:
        if r["frame"] is None:
            continue
        by_cell[(r["model"], r["topic"], r["rung"])][r["frame"]] += 1

    nest: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for (model, _topic, rung), counts in by_cell.items():
        total = sum(counts.values())
        if total == 0:
            nest[model][rung].append(0.0)
            continue
        h = -sum((n / total) * math.log2(n / total) for n in counts.values() if n > 0)
        nest[model][rung].append(h)

    return {
        model: {rung: sum(hs) / len(hs) for rung, hs in by_rung.items()}
        for model, by_rung in nest.items()
    }


def refusal_rate(rows: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    """model → rung → mean refusal rate across topics."""
    by_cell: dict[tuple[str, str, int], list[bool]] = defaultdict(list)
    for r in rows:
        by_cell[(r["model"], r["topic"], r["rung"])].append(r["refused"])

    nest: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for (model, _topic, rung), flags in by_cell.items():
        if not flags:
            continue
        nest[model][rung].append(sum(flags) / len(flags))

    return {
        model: {rung: sum(rs) / len(rs) for rung, rs in by_rung.items()}
        for model, by_rung in nest.items()
    }


def per_cell_sigma(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One row per (model, topic, rung) with σ(stance) for the scatter panel."""
    by_cell: dict[tuple[str, str, int], list[float]] = defaultdict(list)
    for r in rows:
        if r["stance"] is None:
            continue
        by_cell[(r["model"], r["topic"], r["rung"])].append(float(r["stance"]))
    return [
        {
            "model": model,
            "topic": topic,
            "rung": rung,
            "sigma": statistics.pstdev(stances) if len(stances) >= 2 else 0.0,
        }
        for (model, topic, rung), stances in by_cell.items()
    ]


def load_judge_scores() -> dict[tuple[str, int], float] | None:
    """Load the openendedness-judge sidecar (mean of 2 judges per cell)."""
    if not SIDECAR_PATH.exists():
        return None
    try:
        raw = json.loads(SIDECAR_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    out: dict[tuple[str, int], float] = {}
    for key, per_judge in raw.items():
        if "/r" not in key:
            continue
        topic, rung_part = key.split("/r", 1)
        try:
            rung = int(rung_part)
        except ValueError:
            continue
        mean = per_judge.get("mean")
        if mean is None:
            continue
        out[(topic, rung)] = float(mean)
    return out


def _line_panel(
    ax,
    metric: dict[str, dict[int, float]],
    rungs: list[int],
    rung_labels: list[str] | None,
    cmap,
    sorted_models: list[str],
    title: str,
    ylabel: str,
    ymax_floor: float | None = None,
) -> None:
    for i, model in enumerate(sorted_models):
        ys = [metric.get(model, {}).get(r) for r in rungs]
        present = [(r, y) for r, y in zip(rungs, ys, strict=True) if y is not None]
        if not present:
            continue
        xs, ys_ = zip(*present, strict=True)
        ax.plot(
            xs, ys_, marker="o", label=model.split("/")[-1], color=cmap(i % 10), lw=2
        )
    ax.set_xlabel("Question-openendedness rung")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontsize=10)
    ax.set_xticks(rungs)
    if rung_labels and len(rung_labels) == len(rungs):
        ax.set_xticklabels(
            [f"{r}\n{rung_labels[i]}" for i, r in enumerate(rungs)], fontsize=8
        )
    ax.set_ylim(bottom=0)
    if ymax_floor is not None:
        cur_top = ax.get_ylim()[1]
        ax.set_ylim(top=max(cur_top, ymax_floor))
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best", fontsize=8, frameon=False)


def plot(
    sigma: dict[str, dict[int, float]],
    entropy: dict[str, dict[int, float]],
    refused: dict[str, dict[int, float]],
    cells: list[dict[str, Any]],
    judge_scores: dict[tuple[str, int], float] | None,
    out_path: Path,
    rung_labels: list[str] | None = None,
) -> None:
    if not (sigma or entropy or refused):
        print("No data to plot.", file=sys.stderr)
        return

    has_scatter = bool(judge_scores) and bool(cells)
    rungs = sorted({r for d in (sigma, entropy, refused) for by in d.values() for r in by})
    sorted_models = sorted(set(sigma) | set(entropy) | set(refused))
    cmap = plt.get_cmap("tab10")

    if has_scatter:
        fig, axes = plt.subplots(
            nrows=1, ncols=4, figsize=(18, 4.4), dpi=150,
            gridspec_kw={"width_ratios": [1, 1, 1, 1.05]},
        )
    else:
        fig, axes = plt.subplots(nrows=1, ncols=3, figsize=(14, 4.4), dpi=150)

    _line_panel(
        axes[0], sigma, rungs, rung_labels, cmap, sorted_models,
        title="Stance variance\nσ(stance) across N=10 epochs, mean over topics",
        ylabel="σ(stance) — bits of [−1, +1]",
        ymax_floor=0.3,
    )
    _line_panel(
        axes[1], entropy, rungs, rung_labels, cmap, sorted_models,
        title="Frame entropy\nShannon H over frame distribution",
        ylabel="H(frame) [bits]",
        ymax_floor=2.0,
    )
    _line_panel(
        axes[2], refused, rungs, rung_labels, cmap, sorted_models,
        title="Refusal rate\nfraction of N=10 epochs flagged refused/hedged",
        ylabel="refusal rate",
        ymax_floor=0.5,
    )

    if has_scatter:
        ax = axes[3]
        model_to_cells: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for c in cells:
            score = judge_scores.get((c["topic"], c["rung"]))
            if score is None:
                continue
            model_to_cells[c["model"]].append({**c, "x": score})

        for i, model in enumerate(sorted_models):
            mc = model_to_cells.get(model, [])
            if not mc:
                continue
            xs = [c["x"] for c in mc]
            ys = [c["sigma"] for c in mc]
            ax.scatter(
                xs, ys, color=cmap(i % 10), alpha=0.7, s=42,
                label=model.split("/")[-1],
                edgecolor="white", linewidth=0.6,
            )
        rung_to_xs: dict[int, list[float]] = defaultdict(list)
        for (_topic, rung), score in judge_scores.items():
            rung_to_xs[rung].append(score)
        for rung, xs in sorted(rung_to_xs.items()):
            mean_x = sum(xs) / len(xs)
            ax.axvline(mean_x, color="#bbbbbb", lw=0.6, ls=":")
            ax.text(mean_x, 0.005, f"r{rung}",
                    fontsize=8, color="#777777", ha="center", va="bottom")
        ax.set_xlim(-0.05, 1.05)
        ax.set_xlabel("Judge-rated openendedness (0..1)")
        ax.set_ylabel("σ(stance) per (topic, rung) cell")
        ax.set_title("Stance σ vs. judge-openendedness\n(per-cell scatter, validates rungs)", fontsize=10)
        ax.set_ylim(bottom=0)
        ax.grid(True, axis="y", alpha=0.3)
        ax.legend(loc="best", fontsize=8, frameon=False)

    fig.suptitle(
        "Response variance vs. question openendedness "
        "(election policy, 5 topics × 5 rungs × N=10 epochs)",
        fontsize=12, y=1.04,
    )
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    print(f"wrote {out_path}")


def render_metric_table(metric: dict[str, dict[int, float]], name: str) -> str:
    rungs = sorted({r for by_rung in metric.values() for r in by_rung})
    lines = [f"### {name}"]
    lines.append("| model | " + " | ".join(f"r{r}" for r in rungs) + " |")
    lines.append("|---" + "|---:" * len(rungs) + "|")
    for model in sorted(metric.keys()):
        cells = []
        for r in rungs:
            v = metric[model].get(r)
            cells.append(f"{v:.3f}" if v is not None else "—")
        lines.append(f"| `{model}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("log_dir", type=Path, help="inspect-ai log directory (e.g. logs/)")
    p.add_argument(
        "--out", type=Path,
        default=Path("evals/openendedness_ladder/figure.png"),
        help="Output PNG path.",
    )
    args = p.parse_args(argv)

    if not args.log_dir.exists():
        print(f"Log dir not found: {args.log_dir}", file=sys.stderr)
        return 1

    rows = collect(args.log_dir)
    if not rows:
        print(f"No openendedness_ladder rows found in {args.log_dir}.", file=sys.stderr)
        return 1

    sigma = stance_sigma(rows)
    entropy = frame_entropy(rows)
    refused = refusal_rate(rows)
    cells = per_cell_sigma(rows)
    judge_scores = load_judge_scores()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rung_labels = ["factual y/n", "factual trend", "evaluative", "implications", "meta"]
    plot(sigma, entropy, refused, cells, judge_scores, args.out, rung_labels=rung_labels)

    print()
    print(render_metric_table(sigma, "Stance σ (mean across topics)"))
    print()
    print(render_metric_table(entropy, "Frame Shannon H (bits, mean across topics)"))
    print()
    print(render_metric_table(refused, "Refusal rate (mean across topics)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
