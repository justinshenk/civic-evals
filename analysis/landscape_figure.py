"""Generate the CORDA P3 problem-space landscape figure.

Rows: research topics in civic-LLM evaluation.
Cols: existing actors + CORDA P3 (current findings + proposed paper sections).
Cells: 0 = empty, 1 = adjacent/partial, 2 = owns / strong claim.

The figure surfaces the white space where this paper sits — rows where
CORDA P3's proposed sections are filled but no other group has claimed
the row.

Usage::

    uv run python analysis/landscape_figure.py --out site/public/preview/landscape.png

Edit the TOPICS / GROUPS / MATRIX constants when the literature shifts.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as patches  # noqa: E402
import numpy as np  # noqa: E402


TOPICS = [
    "Factual accuracy on civic procedures",
    "Calibrated uncertainty (UQ) on civic facts",
    "Substantive policy bias (answer-side)",
    "Disclosure-mechanics rubrics",
    "Refusal / abstention as object of study",
    "Persona conditioning of responses",
    "Multi-turn / sycophancy dynamics",
    "Persona × pressure interaction",
    "Cross-axis failure concentration",
    "Training fixes for political bias",
    "Downstream civic-participation effects",
]

GROUPS = [
    "Factuality\nbenchmarks\n(TruthfulQA,\nSimpleQA)",
    "LM-Polygraph\n(Vashurin\n+ al., 2025)",
    "Political-bias\naudits\n(Rozado,\nMotoki)",
    "CAIS\n(Phan + al.,\n2026)",
    "Sycophancy\nlit (Sharma,\nPerez + al.)",
    "Persona\ndrift lit\n(Salinas,\nWei + al.)",
    "P6 / Maxi\n(disclosure\nrubric, v1\nMay 2026)",
    "CORDA P3\n(done in\nrepo)",
    "CORDA P3\n(this paper\n§§1–6)",
]

# 0 = empty, 1 = adjacent / partial, 2 = owns / strong claim
# rows = TOPICS, cols = GROUPS
MATRIX = np.array(
    [
        # factual UQ      rozado  cais   sycoph persona  p6     corda  corda
        [   2,    1,        0,    0,      0,     0,      0,      2,    1 ],  # Factual accuracy
        [   1,    2,        0,    0,      0,     0,      1,      2,    1 ],  # Calibrated uncertainty
        [   0,    0,        2,    2,      0,     0,      0,      1,    2 ],  # Substantive policy bias
        [   0,    0,        0,    0,      0,     0,      2,      0,    1 ],  # Disclosure mechanics
        [   0,    0,        0,    0,      0,     0,      1,      2,    2 ],  # Refusal / abstention  ← NOVEL
        [   0,    0,        0,    1,      0,     2,      0,      1,    2 ],  # Persona conditioning
        [   0,    0,        0,    0,      2,     1,      0,      0,    2 ],  # Multi-turn / sycophancy
        [   0,    0,        0,    0,      0,     0,      0,      0,    2 ],  # Persona × pressure ← NOVEL
        [   0,    0,        0,    0,      0,     0,      0,      0,    2 ],  # Cross-axis failure ← NOVEL
        [   0,    0,        1,    2,      0,     0,      0,      0,    0 ],  # Training fixes (out of scope)
        [   0,    0,        0,    0,      0,     0,      0,      0,    0 ],  # Downstream behavior (out of scope)
    ],
    dtype=int,
)

# Mark rows where CORDA P3's *new work* (rightmost column) is the only "owns" claim.
# These are the genuinely novel territory.
NOVEL_ROWS = [4, 7, 8]  # refusal, persona×pressure, cross-axis

# Mark rows that are explicitly out of scope.
OOS_ROWS = [9, 10]  # training fixes, downstream behavior


def render(out_path: Path) -> None:
    assert MATRIX.shape == (len(TOPICS), len(GROUPS)), "matrix shape mismatch"

    fig, ax = plt.subplots(figsize=(13, 7.5), dpi=160)

    # Color cells manually so we get a clean 3-level palette (white / light grey / dark green).
    palette = {0: "#ffffff", 1: "#d6d6d6", 2: "#2b6e3f"}
    for r in range(len(TOPICS)):
        for c in range(len(GROUPS)):
            v = MATRIX[r, c]
            color = palette[v]
            rect = patches.Rectangle(
                (c, len(TOPICS) - 1 - r),
                1,
                1,
                facecolor=color,
                edgecolor="#bbbbbb",
                linewidth=0.7,
            )
            ax.add_patch(rect)
            # Annotation
            if v == 2:
                ax.text(
                    c + 0.5,
                    len(TOPICS) - 1 - r + 0.5,
                    "●",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=11,
                    fontweight="bold",
                )
            elif v == 1:
                ax.text(
                    c + 0.5,
                    len(TOPICS) - 1 - r + 0.5,
                    "○",
                    ha="center",
                    va="center",
                    color="#555555",
                    fontsize=10,
                )

    # Highlight: yellow halo around the rightmost column (corda new) where rows are novel.
    for r in NOVEL_ROWS:
        rect = patches.Rectangle(
            (len(GROUPS) - 1, len(TOPICS) - 1 - r),
            1,
            1,
            facecolor="none",
            edgecolor="#e6a700",
            linewidth=3,
        )
        ax.add_patch(rect)

    # Annotate out-of-scope rows on the right.
    for r in OOS_ROWS:
        ax.text(
            len(GROUPS) + 0.15,
            len(TOPICS) - 1 - r + 0.5,
            "out of scope",
            ha="left",
            va="center",
            color="#999999",
            fontsize=8.5,
            style="italic",
        )

    # Mark novel-row labels with a leading ★ on the left for emphasis.
    topic_labels = []
    for r, t in enumerate(TOPICS):
        if r in NOVEL_ROWS:
            topic_labels.append(f"★  {t}")
        elif r in OOS_ROWS:
            topic_labels.append(t)
        else:
            topic_labels.append(t)

    # Axes setup
    ax.set_xlim(-0.05, len(GROUPS) + 2.1)
    ax.set_ylim(-0.05, len(TOPICS) + 0.05)
    ax.set_xticks([c + 0.5 for c in range(len(GROUPS))])
    ax.set_xticklabels(GROUPS, fontsize=8.5, ha="center")
    ax.set_yticks([len(TOPICS) - 1 - r + 0.5 for r in range(len(TOPICS))])
    ax.set_yticklabels(topic_labels, fontsize=9.5)

    # Separator between existing actors and CORDA P3 columns.
    ax.axvline(x=len(GROUPS) - 2, color="#888888", linestyle="--", linewidth=1.0, alpha=0.6)

    # Move x-axis labels to top
    ax.xaxis.tick_top()
    ax.tick_params(axis="x", which="both", length=0, pad=4)
    ax.tick_params(axis="y", which="both", length=0)

    # Strip top/right spines
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Title + caption
    fig.suptitle(
        "The civic-LLM evaluation landscape · where this paper sits",
        fontsize=13,
        fontweight="bold",
        y=0.99,
    )
    fig.text(
        0.5,
        0.04,
        "● owns / strong claim   ○ adjacent or partial   (blank) empty\n"
        "★ rows where CORDA P3's proposed paper is the only owns-it claim — "
        "the white space being claimed.\n"
        "Existing actors left of the dashed line; CORDA P3's two columns are 'current repo' "
        "(Findings 1 + 2) and 'proposed paper §§1–6'.",
        ha="center",
        fontsize=8.5,
        color="#444444",
    )

    plt.subplots_adjust(top=0.84, bottom=0.18, left=0.34, right=0.97)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    print(f"Wrote {out_path}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        default="site/public/preview/landscape.png",
        help="output PNG path",
    )
    args = ap.parse_args()
    render(Path(args.out))


if __name__ == "__main__":
    main()
