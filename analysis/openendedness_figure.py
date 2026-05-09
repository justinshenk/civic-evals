"""Generate the openendedness-bias figure from openendedness_ladder logs.

Walks ``logs/`` for ``openendedness_ladder`` runs, pulls the per-row
stance values from ``Score.metadata["stance"]``, and renders a
two-panel figure:

- **Left panel**: ``mean over topics of |stance(L) − stance(R)|`` versus
  the *a-priori rung*. One line per model. The rungs widen along
  question openendedness (interpretive ambiguity): r1 is a factual y/n
  with one correct answer; r5 is a broadly unbounded meta-question.
- **Right panel** (when the sidecar exists): per-cell scatter of
  ``|stance(L) − stance(R)|`` vs. *judge-rated openendedness* (read
  from ``evals/openendedness_ladder/openendedness_scores.json``).
  Each point is one ``(topic, rung, model)`` cell. The judge score is
  an LLM-derived 0..1 measurement of the same dimension the rungs
  encode; the scatter validates (or surfaces disagreement with) the
  rung ordering, and lets the bias signal be plotted against a
  continuous predictor instead of a 5-point ordinal.

Usage::

    uv run python analysis/score_openendedness.py    # populate sidecar (one-time)
    uv run python analysis/openendedness_figure.py logs/ \
        --out evals/openendedness_ladder/figure.png

Inputs are inspect-ai ``.eval`` log files; output is a PNG. The script
also prints a small markdown table summarizing the data points in the
figure.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display
import matplotlib.pyplot as plt  # noqa: E402
from inspect_ai.log import list_eval_logs, read_eval_log  # noqa: E402

EVAL_NAME = "openendedness_ladder"
SIDECAR_PATH = Path("evals/openendedness_ladder/openendedness_scores.json")


def collect(log_dir: Path) -> list[dict[str, Any]]:
    """Return one row per (model, topic, rung, framing) cell.

    Skips rows where the scorer flagged a refusal (judge couldn't
    extract a stance) — those would otherwise contaminate the bias
    delta with structural zeros.
    """
    rows: list[dict[str, Any]] = []
    for log_file in list_eval_logs(str(log_dir)):
        log = read_eval_log(log_file)
        if log.eval.task != EVAL_NAME:
            continue
        model = getattr(log.eval, "model", "") or "unknown"
        for sample in log.samples or []:
            scores = sample.scores or {}
            score = scores.get("stance_extraction")
            if score is None:
                continue
            sm = score.metadata or {}
            stance = sm.get("stance")
            if stance is None:
                continue
            # Topic / rung / framing live in the task's extras (loader
            # surfaces them on the sample's metadata.extras).
            extras = (sample.metadata or {}).get("extras") or sm
            rows.append(
                {
                    "model": model,
                    "topic": extras.get("topic") or sm.get("topic"),
                    "rung": int(extras.get("rung") or sm.get("rung") or 0),
                    "framing": extras.get("framing") or sm.get("framing"),
                    "stance": float(stance),
                }
            )
    return rows


def bias_by_rung(rows: list[dict[str, Any]]) -> dict[str, dict[int, float]]:
    """Returns model → rung → mean |stance(L) − stance(R)| across topics."""
    nest: dict[str, dict[int, dict[str, dict[str, float]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    for r in rows:
        if r["framing"] not in ("left", "right"):
            continue
        nest[r["model"]][r["rung"]][r["topic"]][r["framing"]] = r["stance"]

    out: dict[str, dict[int, float]] = {}
    for model, by_rung in nest.items():
        out[model] = {}
        for rung, by_topic in by_rung.items():
            gaps = []
            for _topic, framings in by_topic.items():
                if "left" in framings and "right" in framings:
                    gaps.append(abs(framings["left"] - framings["right"]))
            if gaps:
                out[model][rung] = sum(gaps) / len(gaps)
    return out


def per_cell_gaps(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One row per (model, topic, rung) with the framing-pair gap.

    Used for the scatter panel — each point is one cell, not a
    rung-aggregate. Only includes cells with both L and R observed.
    """
    nest: dict[
        tuple[str, str, int], dict[str, float]
    ] = defaultdict(dict)
    for r in rows:
        if r["framing"] not in ("left", "right"):
            continue
        nest[(r["model"], r["topic"], r["rung"])][r["framing"]] = r["stance"]
    cells: list[dict[str, Any]] = []
    for (model, topic, rung), framings in nest.items():
        if "left" in framings and "right" in framings:
            cells.append(
                {
                    "model": model,
                    "topic": topic,
                    "rung": rung,
                    "gap": abs(framings["left"] - framings["right"]),
                }
            )
    return cells


def load_judge_scores() -> dict[tuple[str, int], float] | None:
    """Load the openendedness-judge sidecar if present.

    Returns a (topic, rung) → mean-judge-score map, or None if the
    sidecar doesn't exist. Falls back gracefully so the figure still
    renders the rung-aggregate panel without judge data.
    """
    if not SIDECAR_PATH.exists():
        return None
    try:
        raw = json.loads(SIDECAR_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    out: dict[tuple[str, int], float] = {}
    for key, per_judge in raw.items():
        # Keys are "<topic>/r<rung>".
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


def plot(
    bias: dict[str, dict[int, float]],
    cells: list[dict[str, Any]],
    judge_scores: dict[tuple[str, int], float] | None,
    out_path: Path,
    rung_labels: list[str] | None = None,
) -> None:
    if not bias:
        print("No data to plot.", file=sys.stderr)
        return

    has_scatter = bool(judge_scores) and bool(cells)
    if has_scatter:
        fig, (ax_left, ax_right) = plt.subplots(
            ncols=2, figsize=(13, 4.8), dpi=160, gridspec_kw={"width_ratios": [1, 1.05]}
        )
    else:
        fig, ax_left = plt.subplots(figsize=(7.5, 4.5), dpi=160)
        ax_right = None

    rungs = sorted({r for by_rung in bias.values() for r in by_rung})
    cmap = plt.get_cmap("tab10")
    sorted_models = sorted(bias.keys())

    # ---- left panel: bias vs. a-priori rung ------------------------------
    for i, model in enumerate(sorted_models):
        ys = [bias[model].get(r) for r in rungs]
        present = [(r, y) for r, y in zip(rungs, ys, strict=True) if y is not None]
        if not present:
            continue
        xs, ys_ = zip(*present, strict=True)
        ax_left.plot(
            xs, ys_, marker="o", label=model.split("/")[-1], color=cmap(i % 10), lw=2
        )
    ax_left.set_xlabel(
        "Question-openendedness rung\n"
        "(1 = factual yes/no, 5 = unbounded meta-question)"
    )
    ax_left.set_ylabel("Mean |stance(L) − stance(R)| across topics")
    ax_left.set_title(
        "By a-priori rung\n($-$1..+1 stance scale, mean across 5 topics)",
        fontsize=10,
    )
    ax_left.set_xticks(rungs)
    if rung_labels and len(rung_labels) == len(rungs):
        ax_left.set_xticklabels(
            [f"{r}\n{rung_labels[i]}" for i, r in enumerate(rungs)], fontsize=9
        )
    ax_left.set_ylim(bottom=0)
    ax_left.grid(True, axis="y", alpha=0.3)
    ax_left.legend(loc="best", fontsize=9, frameon=False)

    # ---- right panel: bias vs. judge-rated openendedness ------------------
    if has_scatter and ax_right is not None:
        # Group cells by model for legend coloring.
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
            ys = [c["gap"] for c in mc]
            ax_right.scatter(
                xs,
                ys,
                color=cmap(i % 10),
                alpha=0.7,
                s=42,
                label=model.split("/")[-1],
                edgecolor="white",
                linewidth=0.6,
            )

        # Faint vertical lines marking the 5 rung-mean judge scores so the
        # reader can see how the rung-aggregate maps onto the continuous axis.
        rung_to_xs: dict[int, list[float]] = defaultdict(list)
        for (_topic, rung), score in judge_scores.items():
            rung_to_xs[rung].append(score)
        for rung, xs in sorted(rung_to_xs.items()):
            mean_x = sum(xs) / len(xs)
            ax_right.axvline(mean_x, color="#bbbbbb", lw=0.6, ls=":")
            ax_right.text(
                mean_x,
                ax_right.get_ylim()[1] if False else 0.005,  # bottom
                f"r{rung}",
                fontsize=8,
                color="#777777",
                ha="center",
                va="bottom",
            )

        ax_right.set_xlim(-0.05, 1.05)
        ax_right.set_xlabel("Judge-rated openendedness (0 = factual, 1 = unbounded)")
        ax_right.set_ylabel("|stance(L) − stance(R)| per (topic, rung) cell")
        ax_right.set_title(
            "By judge-rated openendedness\n(per-cell, validates rung ordering)",
            fontsize=10,
        )
        ax_right.set_ylim(bottom=0)
        ax_right.grid(True, axis="y", alpha=0.3)
        ax_right.legend(loc="best", fontsize=9, frameon=False)

    fig.suptitle(
        "Framing-induced stance bias vs. question openendedness "
        "(election policy, 5 topics)",
        fontsize=12,
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    print(f"wrote {out_path}")


def render_markdown_table(bias: dict[str, dict[int, float]]) -> str:
    """Compact markdown summary of the rung-aggregate panel."""
    rungs = sorted({r for by_rung in bias.values() for r in by_rung})
    lines = []
    lines.append("| model | " + " | ".join(f"r{r}" for r in rungs) + " |")
    lines.append("|---" + "|---:" * len(rungs) + "|")
    for model in sorted(bias.keys()):
        cells = []
        for r in rungs:
            v = bias[model].get(r)
            cells.append(f"{v:.3f}" if v is not None else "—")
        lines.append(f"| `{model}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_judge_table(judge_scores: dict[tuple[str, int], float]) -> str:
    """Markdown table of judge openendedness by (topic, rung)."""
    topics = sorted({t for (t, _r) in judge_scores})
    rungs = sorted({r for (_t, r) in judge_scores})
    lines = []
    lines.append("| topic | " + " | ".join(f"r{r}" for r in rungs) + " |")
    lines.append("|---" + "|---:" * len(rungs) + "|")
    for topic in topics:
        cells = [
            f"{judge_scores[(topic, r)]:.2f}" if (topic, r) in judge_scores else "—"
            for r in rungs
        ]
        lines.append(f"| `{topic}` | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("log_dir", type=Path, help="inspect-ai log directory (e.g. logs/)")
    p.add_argument(
        "--out",
        type=Path,
        default=Path("evals/openendedness_ladder/figure.png"),
        help="Output PNG path.",
    )
    args = p.parse_args(argv)

    if not args.log_dir.exists():
        print(f"Log dir not found: {args.log_dir}", file=sys.stderr)
        return 1

    rows = collect(args.log_dir)
    if not rows:
        print(
            f"No openendedness_ladder rows found in {args.log_dir}.",
            file=sys.stderr,
        )
        return 1

    bias = bias_by_rung(rows)
    cells = per_cell_gaps(rows)
    judge_scores = load_judge_scores()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    rung_labels = ["factual y/n", "factual trend", "evaluative", "implications", "meta"]
    plot(bias, cells, judge_scores, args.out, rung_labels=rung_labels)
    print()
    print(render_markdown_table(bias))
    if judge_scores:
        print()
        print("Judge-rated openendedness (mean of 2 judges, 0..1):")
        print(render_judge_table(judge_scores))
    else:
        print(
            "\n(Judge openendedness sidecar not found at "
            f"{SIDECAR_PATH}; right panel skipped. "
            "Run `uv run python analysis/score_openendedness.py` to populate.)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
