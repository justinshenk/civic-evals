"""Generate the openendedness-bias figure from openendedness_ladder logs.

Walks ``logs/`` for ``openendedness_ladder`` runs, pulls the per-row
stance values from ``Score.metadata["stance"]``, and plots
``mean over topics of |stance(L) − stance(R)|`` versus rung — one
line per model. The hypothesis is that bias should be near-zero at
rung 1 (yes/no — no room for framing to land) and grow as the rung
opens up.

Usage::

    uv run python analysis/openendedness_figure.py logs/ \
        --out evals/openendedness_ladder/figure.png

Inputs are inspect-ai ``.eval`` log files; output is a PNG. The
script also prints a small markdown table summarizing the data points
in the figure for paste-into-PR consumption.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # no display
import matplotlib.pyplot as plt  # noqa: E402
from inspect_ai.log import list_eval_logs, read_eval_log  # noqa: E402

EVAL_NAME = "openendedness_ladder"


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
    """Returns model → rung → mean |stance(L) − stance(R)| across topics.

    Only includes rungs where every topic has both a left and a right
    stance available (otherwise the mean is biased by which topics are
    missing). This is the "honest" reduction; the alternative
    "best-effort" reduction is computed separately downstream if
    needed.
    """
    # model → rung → topic → framing → stance
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


def plot(
    bias: dict[str, dict[int, float]],
    out_path: Path,
    rung_labels: list[str] | None = None,
) -> None:
    if not bias:
        print("No data to plot.", file=sys.stderr)
        return

    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=160)
    rungs = sorted({r for by_rung in bias.values() for r in by_rung})

    # Stable color cycle by sorted model id so re-runs produce the same
    # color per provider.
    cmap = plt.get_cmap("tab10")
    for i, model in enumerate(sorted(bias.keys())):
        ys = [bias[model].get(r) for r in rungs]
        # Drop None gaps so partial coverage doesn't break the plot,
        # but warn — the figure should not silently misrepresent.
        present = [(r, y) for r, y in zip(rungs, ys, strict=True) if y is not None]
        if not present:
            continue
        xs, ys_ = zip(*present, strict=True)
        ax.plot(xs, ys_, marker="o", label=model.split("/")[-1], color=cmap(i % 10), lw=2)

    ax.set_xlabel("Openendedness rung (1 = yes/no, 5 = open prose)")
    ax.set_ylabel("Mean |stance(L) − stance(R)| across topics")
    ax.set_title(
        "Framing-induced stance bias vs. response openendedness\n"
        "(election policy, 5 topics, $-$1..+1 stance scale)",
        fontsize=11,
    )
    ax.set_xticks(rungs)
    if rung_labels and len(rung_labels) == len(rungs):
        ax.set_xticklabels(
            [f"{r}\n{rung_labels[i]}" for i, r in enumerate(rungs)], fontsize=9
        )
    ax.set_ylim(bottom=0)
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(loc="best", fontsize=9, frameon=False)

    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    print(f"wrote {out_path}")


def render_markdown_table(bias: dict[str, dict[int, float]]) -> str:
    """Compact markdown summary of the figure's data points."""
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
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rung_labels = ["yes/no", "1-sent", "pros/cons", "paragraph", "open"]
    plot(bias, args.out, rung_labels=rung_labels)
    print()
    print(render_markdown_table(bias))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
