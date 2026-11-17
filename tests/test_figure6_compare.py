from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "analysis"))

from figure6_compare import compare  # noqa: E402


def _rows(d_gap: float) -> list[dict]:
    rows = []
    for party in ("Democrat", "Republican"):
        for package in ("D-typical", "R-typical"):
            for exp in ("junior", "mid", "senior"):
                for rigor in ("thin", "deep"):
                    for rep in range(5):
                        rows.append(
                            {
                                "model": "test",
                                "party": party,
                                "policy_package": package,
                                "experience": exp,
                                "rigor": rigor,
                                "rep": rep,
                                "rating": 6.0 + (d_gap if package == "D-typical" else 0),
                            }
                        )
    return rows


def test_compare_recovers_gap_reduction() -> None:
    result = compare(_rows(2.0), _rows(0.5))
    assert result["base"]["mean_package_gap"] == 2.0
    assert result["pct"]["mean_package_gap"] == 0.5
    assert result["change"]["mean"] == -1.5
    assert result["change"]["relative_gap_reduction"] == 0.75
