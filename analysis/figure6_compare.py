"""Paired, prompt-level comparison of Qwen3-14B base versus PCT.

The generation driver reports each arm descriptively. This script performs
the Figure 6 estimand: how much PCT changes the D-typical minus R-typical
rating gap, using the 12 matched (party, experience, rigor) strata as the
inferential units. Repeated generations are averaged within each prompt.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from multi_model_bias import fit_model  # noqa: E402


@dataclass
class ArmSummary:
    name: str
    n_rows: int
    n_parsed: int
    mean_package_gap: float
    gap_ci95: tuple[float, float]
    paired_p: float
    beta_package: float
    years_per_package: float | None


def _load(path: Path) -> list[dict]:
    rows = json.loads(path.read_text())
    if not isinstance(rows, list):
        raise ValueError(f"{path} is not a JSON list")
    return rows


def _cell_means(rows: list[dict]) -> dict[tuple[str, str, str, str], float]:
    grouped: dict[tuple[str, str, str, str], list[float]] = {}
    for row in rows:
        if not isinstance(row.get("rating"), (int, float)):
            continue
        key = (
            row["party"], row["policy_package"], row["experience"], row["rigor"]
        )
        grouped.setdefault(key, []).append(float(row["rating"]))
    return {key: float(np.mean(values)) for key, values in grouped.items()}


def _package_gaps(rows: list[dict]) -> tuple[list[tuple[str, str, str]], np.ndarray]:
    means = _cell_means(rows)
    strata = sorted({(p, e, r) for p, _, e, r in means})
    gaps = []
    for party, exp, rigor in strata:
        gaps.append(
            means[(party, "D-typical", exp, rigor)]
            - means[(party, "R-typical", exp, rigor)]
        )
    return strata, np.asarray(gaps, dtype=float)


def _ci(values: np.ndarray) -> tuple[float, float]:
    mean = float(values.mean())
    sem = float(stats.sem(values))
    if np.isclose(sem, 0.0):
        return mean, mean
    lo, hi = stats.t.interval(0.95, len(values) - 1, loc=mean, scale=sem)
    return float(lo), float(hi)


def _one_sample_p(values: np.ndarray) -> float:
    if np.allclose(values, values[0]):
        return 0.0 if not np.isclose(values[0], 0.0) else 1.0
    return float(stats.ttest_1samp(values, 0.0).pvalue)


def _exact_sign_flip_p(values: np.ndarray) -> float:
    observed = abs(float(values.mean()))
    exceed = 0
    total = 1 << len(values)
    for mask in range(total):
        signed = [v if mask & (1 << i) else -v for i, v in enumerate(values)]
        exceed += abs(float(np.mean(signed))) >= observed - 1e-12
    return exceed / total


def compare(base_rows: list[dict], pct_rows: list[dict]) -> dict:
    base_strata, base_gaps = _package_gaps(base_rows)
    pct_strata, pct_gaps = _package_gaps(pct_rows)
    if base_strata != pct_strata or len(base_strata) != 12:
        raise ValueError("arms do not contain the same complete 12 matched strata")

    base_fit = fit_model(base_rows, "base")
    pct_fit = fit_model(pct_rows, "pct")
    change = pct_gaps - base_gaps

    def arm(name: str, rows: list[dict], gaps: np.ndarray, fit) -> ArmSummary:
        return ArmSummary(
            name=name,
            n_rows=len(rows),
            n_parsed=sum(isinstance(r.get("rating"), (int, float)) for r in rows),
            mean_package_gap=float(gaps.mean()),
            gap_ci95=_ci(gaps),
            paired_p=_one_sample_p(gaps),
            beta_package=float(fit.beta_std["policy_package"]),
            years_per_package=fit.years_per_package,
        )

    base = arm("base", base_rows, base_gaps, base_fit)
    pct = arm("pct", pct_rows, pct_gaps, pct_fit)
    reduction = 1.0 - pct.mean_package_gap / base.mean_package_gap
    return {
        "estimand": "PCT minus base change in D-typical minus R-typical rating gap",
        "unit": "12 matched (party, experience, rigor) prompt strata",
        "base": asdict(base),
        "pct": asdict(pct),
        "change": {
            "mean": float(change.mean()),
            "ci95": _ci(change),
            "paired_t_p": _one_sample_p(change),
            "exact_sign_flip_p": _exact_sign_flip_p(change),
            "relative_gap_reduction": float(reduction),
            "stratum_changes": change.tolist(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base", type=Path)
    parser.add_argument("pct", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()
    result = compare(_load(args.base), _load(args.pct))
    args.out.write_text(json.dumps(result, indent=2))
    if args.markdown:
        base = result["base"]
        pct = result["pct"]
        change = result["change"]
        lines = [
            "# Figure 6 audited comparison — base Qwen3-14B vs PCT",
            "",
            "Inference uses 12 matched `(party, experience, rigor)` prompt strata; "
            "five generations are averaged within each prompt before testing.",
            "",
            "| arm | parsed | D-typical − R-typical gap | 95% CI | prompt-level p | β package | years/package |",
            "|---|---:|---:|---:|---:|---:|---:|",
            f"| Base | {base['n_parsed']}/{base['n_rows']} | {base['mean_package_gap']:.3f} | "
            f"[{base['gap_ci95'][0]:.3f}, {base['gap_ci95'][1]:.3f}] | {base['paired_p']:.4g} | "
            f"{base['beta_package']:.3f} | {base['years_per_package']:.2f} |",
            f"| PCT | {pct['n_parsed']}/{pct['n_rows']} | {pct['mean_package_gap']:.3f} | "
            f"[{pct['gap_ci95'][0]:.3f}, {pct['gap_ci95'][1]:.3f}] | {pct['paired_p']:.4g} | "
            f"{pct['beta_package']:.3f} | {pct['years_per_package']:.2f} |",
            "",
            "## Treatment contrast",
            "",
            f"PCT changed the package gap by **{change['mean']:.3f} points** "
            f"(95% CI [{change['ci95'][0]:.3f}, {change['ci95'][1]:.3f}]; "
            f"paired t p={change['paired_t_p']:.4g}; exact sign-flip p={change['exact_sign_flip_p']:.4g}).",
            f"This is an **{100 * change['relative_gap_reduction']:.1f}% reduction** in the mean gap.",
            "",
            "## Interpretation boundary",
            "",
            "This supports transfer from PCT to this candidate-rating task. It does not establish "
            "that all candidate-judgment bias is fixed: the experiment uses one school-board "
            "scenario selected after earlier work found a large package effect, only 12 matched "
            "prompt strata, and synthetic profiles with some office-history inconsistencies.",
            "",
        ]
        args.markdown.write_text("\n".join(lines))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
