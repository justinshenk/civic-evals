"""Render the audited base-vs-PCT candidate-rating comparison."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = json.loads(args.comparison.read_text())
    change = np.asarray(result["change"]["stratum_changes"], dtype=float)
    base_mean = float(result["base"]["mean_package_gap"])
    pct_mean = float(result["pct"]["mean_package_gap"])

    # The comparison artifact stores treatment changes. Recover paired stratum
    # gaps from the raw rows next to it to keep the plot tied to audited data.
    root = args.comparison.parent
    base_rows = json.loads((root / "qwen3_14b_base_audited_rows.json").read_text())
    pct_rows = json.loads((root / "qwen3_14b_pct_audited_rows.json").read_text())

    def gaps(rows: list[dict]) -> np.ndarray:
        cells: dict[tuple[str, str, str, str], list[float]] = {}
        for row in rows:
            key = (
                row["party"], row["policy_package"], row["experience"], row["rigor"]
            )
            cells.setdefault(key, []).append(float(row["rating"]))
        strata = sorted({(p, e, r) for p, _, e, r in cells})
        return np.asarray(
            [
                np.mean(cells[(p, "D-typical", e, r)])
                - np.mean(cells[(p, "R-typical", e, r)])
                for p, e, r in strata
            ]
        )

    base_gaps = gaps(base_rows)
    pct_gaps = gaps(pct_rows)
    if not np.allclose(pct_gaps - base_gaps, change):
        raise ValueError("raw rows do not match comparison artifact")

    fig, ax = plt.subplots(figsize=(5.2, 4.0))
    for b, p in zip(base_gaps, pct_gaps, strict=True):
        ax.plot([0, 1], [b, p], color="#9aa3ad", alpha=0.55, linewidth=1)
    ax.scatter(np.zeros_like(base_gaps), base_gaps, color="#c44e52", s=25, zorder=3)
    ax.scatter(np.ones_like(pct_gaps), pct_gaps, color="#4c72b0", s=25, zorder=3)

    for x, arm, mean, color in (
        (0, result["base"], base_mean, "#8f1d21"),
        (1, result["pct"], pct_mean, "#214e85"),
    ):
        lo, hi = arm["gap_ci95"]
        ax.errorbar(
            x,
            mean,
            yerr=[[mean - lo], [hi - mean]],
            fmt="D",
            color=color,
            markerfacecolor="white",
            markersize=7,
            linewidth=2.2,
            capsize=5,
            zorder=4,
        )

    ax.axhline(0, color="black", linewidth=0.9, linestyle="--")
    ax.set_xticks([0, 1], ["Base Qwen3-14B", "Qwen3-14B + PCT"])
    ax.set_ylabel("Candidate-rating gap\n(D-typical − R-typical)")
    ax.set_xlim(-0.35, 1.35)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title("Political Consistency Training reduces candidate-rating disparity")
    ax.text(
        0.5,
        0.98,
        f"{100 * result['change']['relative_gap_reduction']:.1f}% reduction; "
        f"paired p={result['change']['paired_t_p']:.3g}",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=9,
    )
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=300, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
