"""Render the persona_drift_pilot figure for the preview page.

Two-panel chart:
- Left: per-axis aggregate |Δstance| (bar) — the pilot's headline.
- Right: per-(topic, axis) heatmap of signed drift, so the reader can see
  which cells are doing the work.

Reads ``analysis/persona_drift_pilot_results.json`` (produced by
``persona_drift_rollup.py``) and writes
``site/public/preview/persona_drift_pilot.png``.

Usage::

    uv run python analysis/persona_drift_figure.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


REPO = Path(__file__).resolve().parents[1]
RESULTS_JSON = REPO / "analysis" / "persona_drift_pilot_results.json"
OUT_PATH = REPO / "site" / "public" / "preview" / "persona_drift_pilot.png"


_AXIS_LABEL = {
    "persona_attribute": "Axis 1\npersona-attribute",
    "sycophantic_pressure": "Axis 2\nsycophantic pressure",
    "false_prior": "Axis 3\nfalse prior",
}
_AXIS_ORDER = ["persona_attribute", "sycophantic_pressure", "false_prior"]


def render(out_path: Path, results_json: Path = RESULTS_JSON) -> None:
    results = json.loads(results_json.read_text())
    cells = results["cells"]
    agg = results["axis_aggregate"]
    topics = results["topics"]
    model = results["model"]
    n_samples = results["n_samples"]
    epochs = results["epochs"]

    axes_order = [a for a in _AXIS_ORDER if a in agg]

    fig, (ax_bar, ax_heat) = plt.subplots(
        1, 2, figsize=(13, 5.2), dpi=160, gridspec_kw={"width_ratios": [1, 2.1]}
    )

    # --- Left panel: per-axis aggregate |Δ| bar
    bar_vals = [agg[a]["mean_drift_abs"] for a in axes_order]
    bar_max = [agg[a]["max_drift_abs"] for a in axes_order]
    colors = ["#9e9e9e", "#9e9e9e", "#2b6e3f"]
    xpos = np.arange(len(axes_order))
    ax_bar.bar(xpos, bar_vals, color=colors, edgecolor="#444444", linewidth=0.6, width=0.6)
    # Annotate max (the most extreme single-topic drift) as a thin marker on top
    for i, m in enumerate(bar_max):
        ax_bar.plot([xpos[i] - 0.22, xpos[i] + 0.22], [m, m], color="#222222", linewidth=1.3)
        ax_bar.text(xpos[i], m + 0.02, f"max {m:+.2f}", ha="center", fontsize=8, color="#444")
    ax_bar.set_xticks(xpos)
    ax_bar.set_xticklabels([_AXIS_LABEL[a] for a in axes_order], fontsize=9)
    ax_bar.set_ylim(0, max(0.7, max(bar_max) + 0.1))
    ax_bar.set_ylabel("Mean |Δ stance|  (5 topics)", fontsize=10)
    ax_bar.set_title("Per-axis drift", fontsize=11, fontweight="bold", pad=10)
    for spine in ("top", "right"):
        ax_bar.spines[spine].set_visible(False)
    ax_bar.tick_params(axis="y", which="both", length=3)
    ax_bar.grid(axis="y", color="#eeeeee", linewidth=0.7, zorder=0)
    ax_bar.set_axisbelow(True)

    # --- Right panel: signed-drift heatmap
    matrix = np.zeros((len(topics), len(axes_order)))
    for r, t in enumerate(topics):
        for c, a in enumerate(axes_order):
            cell = cells.get(t, {}).get(a)
            if cell:
                matrix[r, c] = cell["drift_signed"]

    abs_max = max(0.6, float(np.abs(matrix).max()))
    im = ax_heat.imshow(
        matrix, aspect="auto", cmap="RdBu_r", vmin=-abs_max, vmax=abs_max,
    )
    ax_heat.set_xticks(np.arange(len(axes_order)))
    ax_heat.set_xticklabels([_AXIS_LABEL[a] for a in axes_order], fontsize=9)
    ax_heat.set_yticks(np.arange(len(topics)))
    ax_heat.set_yticklabels(topics, fontsize=9)
    for r in range(len(topics)):
        for c in range(len(axes_order)):
            v = matrix[r, c]
            color = "white" if abs(v) > abs_max * 0.55 else "#333333"
            ax_heat.text(c, r, f"{v:+.2f}", ha="center", va="center", color=color, fontsize=9)
    ax_heat.set_title("Per-(topic, axis) signed Δ stance", fontsize=11, fontweight="bold", pad=10)
    for spine in ax_heat.spines.values():
        spine.set_visible(False)
    ax_heat.tick_params(axis="x", which="both", length=0)
    ax_heat.tick_params(axis="y", which="both", length=0)
    # Lighter gridlines between cells
    ax_heat.set_xticks(np.arange(-0.5, len(axes_order), 1), minor=True)
    ax_heat.set_yticks(np.arange(-0.5, len(topics), 1), minor=True)
    ax_heat.grid(which="minor", color="#dddddd", linewidth=0.7)

    cbar = fig.colorbar(im, ax=ax_heat, fraction=0.04, pad=0.02)
    cbar.set_label("Δ stance  (treatment − baseline)", fontsize=9)
    cbar.ax.tick_params(labelsize=8)

    fig.suptitle(
        "Persona-drift pilot — three-axis decomposition · "
        f"{model.split('/')[-1]} · n={n_samples} (30 tasks × {epochs} epochs)",
        fontsize=11.5,
        fontweight="bold",
        y=1.01,
    )
    fig.text(
        0.5,
        -0.04,
        "Stance scored by stance_extraction on the model's final response (judge = different provider).\n"
        "false_prior dominates because the model either auto-refutes the premise (voter_id, ▼0.57) or quietly folds it into a hedge.\n"
        "Persona and pressure axes show ≈0 drift here — see TAXONOMY.md for the methodological caveats.",
        ha="center",
        fontsize=8.5,
        color="#444444",
    )

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    print(f"Wrote {out_path.relative_to(REPO)}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args()
    render(args.out)


if __name__ == "__main__":
    main()
