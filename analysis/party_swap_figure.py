"""Render the party-swap teaser (paper Figure 1).

Swapping only the party label barely moves a candidate's rating; swapping only
the policy package moves it a lot. Plotted from the six-model factorial run in
``analysis/multi_model_rows.json`` -- no new runs.

Each effect is a difference in mean rating (Republican minus Democrat) within
one model, computed from the 24 cell means (party x policy x experience x rigor)
rather than raw rows. A few ratings failed to parse, mostly in junior cells for
Llama; averaging cell means keeps the other factors balanced so they cancel out
of each difference. The figure shows point estimates only; 95% percentile-bootstrap
intervals (resampling ratings within each cell, seeded) are printed to the console
for reporting in the text.

Writes ``analysis/figures/party_swap_teaser.pdf`` and a ``.png`` sibling.

Usage::

    uv run python analysis/party_swap_figure.py
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
ROWS_JSON = REPO / "analysis" / "multi_model_rows.json"
OUT_PATH = REPO / "analysis" / "figures" / "party_swap_teaser.pdf"

LABEL_COLOR = "#9a9993"  # muted gray: the swap that barely matters
POLICY_COLOR = "#6250d6"  # violet accent: party-neutral (not red/blue)
INK = "#1f1f1d"
INK_2 = "#52514e"


_FACTORS = ("party", "policy_package", "experience", "rigor")


def _mean_diff(cells: dict[tuple, float], idx: int, rep_value: str, dem_value: str) -> float:
    rep = [v for k, v in cells.items() if k[idx] == rep_value]
    dem = [v for k, v in cells.items() if k[idx] == dem_value]
    return float(np.mean(rep) - np.mean(dem))


def _ratings_by_cell(rows_json: Path) -> dict[str, dict[tuple, np.ndarray]]:
    """Return {model: {cell: parsed ratings}}, asserting all 24 cells are present."""
    rows = [r for r in json.loads(rows_json.read_text()) if r["rating"] is not None]
    out: dict[str, dict[tuple, np.ndarray]] = {}
    for model in sorted({r["model"] for r in rows}):
        by_cell: dict[tuple, list[float]] = {}
        for r in rows:
            if r["model"] == model:
                by_cell.setdefault(tuple(r[f] for f in _FACTORS), []).append(r["rating"])
        assert len(by_cell) == 24, f"{model}: expected 24 cells, got {len(by_cell)}"
        out[model] = {k: np.array(v) for k, v in by_cell.items()}
    return out


def _effects(cells: dict[tuple, float]) -> tuple[float, float]:
    return (
        _mean_diff(cells, 0, "Republican", "Democrat"),
        _mean_diff(cells, 1, "R-typical", "D-typical"),
    )


def compute_effects(rows_json: Path = ROWS_JSON) -> dict[str, tuple[float, float]]:
    """Return {model: (label_effect, policy_effect)}, Republican minus Democrat."""
    return {
        model: _effects({k: float(v.mean()) for k, v in cells.items()})
        for model, cells in _ratings_by_cell(rows_json).items()
    }


def bootstrap_cis(
    rows_json: Path = ROWS_JSON, n_boot: int = 2000, seed: int = 0
) -> dict[str, np.ndarray]:
    """Return {model: [[label_lo, label_hi], [policy_lo, policy_hi]]}, 95% percentile CIs.

    Resamples ratings with replacement within each cell, so every replicate keeps
    the balanced 24-cell design.
    """
    rng = np.random.default_rng(seed)
    cis = {}
    for model, cells in _ratings_by_cell(rows_json).items():
        draws = np.array([
            _effects({k: float(rng.choice(v, len(v)).mean()) for k, v in cells.items()})
            for _ in range(n_boot)
        ])
        cis[model] = np.percentile(draws, [2.5, 97.5], axis=0).T
    return cis



_DISPLAY_NAME = {
    "anthropic/claude-haiku-4.5": "Claude Haiku 4.5",
    "deepseek/deepseek-chat": "DeepSeek Chat",
    "google/gemini-2.5-flash": "Gemini 2.5 Flash",
    "meta-llama/llama-3.3-70b-instruct": "Llama 3.3 70B",
    "openai/gpt-4o-mini": "GPT-4o mini",
    "qwen/qwen-2.5-72b-instruct": "Qwen 2.5 72B",
}

CAPTION = (
    "Figure 1. Six LLMs rated fictional school-board candidates on a 1\u201310 scale. Each dot is a model\u2019s average\n"
    "change in rating when one attribute is switched from Democratic to Republican, with everything else kept the\n"
    "same: the party label alone (gray) or the policy platform alone (violet). Averages are over 12 matched pairs of\n"
    "candidates, 5 ratings each."
)


def render(out_path: Path, rows_json: Path = ROWS_JSON, caption: bool = True) -> None:
    effects = compute_effects(rows_json)
    cis = bootstrap_cis(rows_json)
    # Largest policy effect at the top (rows are drawn top-down after invert_yaxis).
    models = sorted(effects, key=lambda m: effects[m][1])
    label = np.array([effects[m][0] for m in models])
    policy = np.array([effects[m][1] for m in models])

    print(f"{'model':36s} {'label swap':>11s} {'95% CI':>16s} {'policy swap':>12s} {'95% CI':>16s}")
    for m in models:
        (llo, lhi), (plo, phi) = cis[m]
        print(f"{m:36s} {effects[m][0]:+11.2f} [{llo:+.2f}, {lhi:+.2f}] "
              f"{effects[m][1]:+12.2f} [{plo:+.2f}, {phi:+.2f}]")
    print(f"{'mean across models':36s} {label.mean():+11.2f} {policy.mean():+12.2f}")

    names = [_DISPLAY_NAME.get(m, m.split("/")[-1]) for m in models]
    ys = np.arange(len(models), dtype=float)

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 9,
        "pdf.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    ax.axvline(0, color=INK_2, linewidth=0.8, zorder=1)

    # Gray line joining each model's two dots, so the gap reads at a glance.
    for y, a, b in zip(ys, label, policy, strict=True):
        ax.plot([a, b], [y, y], color="#d9d8d3", linewidth=2.4,
                solid_capstyle="round", zorder=2)
    for vals, color, name in ((label, LABEL_COLOR, "Party label only, Dem \u2192 Rep"),
                              (policy, POLICY_COLOR, "Policies only, Dem \u2192 Rep")):
        ax.scatter(vals, ys, s=60, color=color, edgecolor="white", linewidth=1.2,
                   zorder=3, label=name)

    ax.set_yticks(ys)
    ax.set_yticklabels(names, color=INK)
    ax.invert_yaxis()
    ax.set_ylim(ys[-1] + 0.6, -0.6)

    ax.set_xlim(min(-1.5, policy.min() - 0.12), max(0.15, label.max() + 0.1))
    ax.set_xticks(np.arange(-1.5, 0.01, 0.25))
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: ("0" if abs(v) < 1e-9 else f"{v:.2f}").replace("-", "\u2212")))
    ax.set_xlabel("Change in rating (points on 1\u201310 scale)", color=INK_2, labelpad=6)
    ax.tick_params(axis="y", length=0, pad=8)
    ax.tick_params(axis="x", length=3, colors=INK_2)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#bdbcb6")
    ax.grid(axis="x", color="#ecebe7", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)

    handles, labels = ax.get_legend_handles_labels()

    fig.suptitle("LLM candidate ratings: party label swap vs. policy swap",
                 x=0.5, ha="center", fontsize=12, fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.25 if caption else 0.08, 1, 1))
    fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, fontsize=8.5,
               handletextpad=0.3, columnspacing=2.0,
               bbox_to_anchor=(0.5, 0.155 if caption else 0.0))
    if caption:
        fig.text(0.5, 0.0, CAPTION, ha="center", va="bottom", multialignment="center", fontsize=7.5, color=INK_2,
                 linespacing=1.4)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight", facecolor="white")
    png_path = out_path.with_suffix(".png")
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    shown = [p.relative_to(REPO) if p.is_relative_to(REPO) else p for p in (out_path, png_path)]
    print(f"Wrote {shown[0]} and {shown[1]}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    ap.add_argument("--no-caption", action="store_true",
                    help="omit the 'Figure 1.' caption (e.g. when LaTeX \\caption supplies it)")
    args = ap.parse_args()
    render(args.out, caption=not args.no_caption)


if __name__ == "__main__":
    main()
