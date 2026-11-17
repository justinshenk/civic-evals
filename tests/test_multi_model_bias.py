"""Offline tests for the multi_model_bias driver + backends.

No GPU / API calls. Local backend construction is not exercised here —
that path is covered by the manual MIG smoke and the full Step 1 run.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "analysis"))

from bias_backends import RateRequest, RateResult, strip_thinking  # noqa: E402
from multi_model_bias import (  # noqa: E402
    FitResult,
    build_parser,
    fit_model,
    gate_decision,
    gather_for_model,
    iter_cells,
    paired_package_inference,
    row_key,
)

# ---- strip_thinking -------------------------------------------------------


def test_strip_thinking_removes_qwen_block() -> None:
    text = "<think>\nlong chain of thought\n</think>\n\nRATING: 7"
    assert strip_thinking(text) == "RATING: 7"


def test_strip_thinking_noop_without_block() -> None:
    assert strip_thinking("RATING: 4") == "RATING: 4"


# ---- factorial ------------------------------------------------------------


def test_iter_cells_full_factorial_is_24() -> None:
    cells = iter_cells()
    assert len(cells) == 24
    keys = {(p, pkg, e, r) for p, pkg, e, r, _ in cells}
    assert len(keys) == 24


def test_iter_cells_smoke_is_one() -> None:
    cells = iter_cells(smoke=True)
    assert len(cells) == 1
    party, package, exp, rigor, profile = cells[0]
    assert party == "Democrat"
    assert package == "D-typical"
    assert exp == "mid"
    assert rigor == "deep"
    assert "RATING:" in profile


# ---- gate -----------------------------------------------------------------


def _fit(**overrides) -> FitResult:
    base = dict(
        model="test",
        n_total=120,
        n_parsed=120,
        rating_mean=6.0,
        rating_sd=1.0,
        r2_std=0.7,
        beta_std={"policy_package": -0.35, "party": 0.0, "party_x_pkg": 0.0},
        se_std={},
        p_std={"policy_package": 1e-10, "party": 0.5, "party_x_pkg": 0.5},
        ci_std={},
        beta_raw={},
        se_raw={},
        years_per_party=0.0,
        years_per_package=7.0,
    )
    base.update(overrides)
    return FitResult(**base)


def test_gate_keep_on_clear_lean() -> None:
    decision = gate_decision(_fit())
    assert decision.startswith("KEEP")


def test_gate_drop_on_weak_lean() -> None:
    decision = gate_decision(
        _fit(
            beta_std={"policy_package": -0.05, "party": 0.0, "party_x_pkg": 0.0},
            p_std={"policy_package": 0.4, "party": 0.5, "party_x_pkg": 0.5},
            years_per_package=0.5,
        )
    )
    assert decision.startswith("DROP")


def test_gate_drop_on_insufficient_n() -> None:
    decision = gate_decision(_fit(n_parsed=10, n_total=120, beta_std={}, p_std={}))
    assert "insufficient" in decision.lower()


# ---- CLI ------------------------------------------------------------------


def test_cli_defaults_openrouter() -> None:
    args = build_parser().parse_args([])
    assert args.backend == "openrouter"
    assert args.thinking == "default"
    assert args.reps == 5


def test_cli_local_figure6_flags() -> None:
    args = build_parser().parse_args(
        [
            "--backend",
            "local",
            "--models",
            "Qwen/Qwen3-14B",
            "--thinking",
            "off",
            "--out",
            "analysis/qwen3_14b_base_rows.json",
            "--smoke",
        ]
    )
    assert args.backend == "local"
    assert args.models == ["Qwen/Qwen3-14B"]
    assert args.thinking == "off"
    assert args.smoke is True


# ---- gather + resume with a fake backend ----------------------------------


class _FakeBackend:
    name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    async def rate(self, request: RateRequest) -> RateResult:
        self.calls += 1
        return RateResult(
            text="Because reasons.\n\nRATING: 6",
            rating=6.0,
            backend=self.name,
            thinking=False,
        )

    async def aclose(self) -> None:
        return None


def test_gather_smoke_one_call() -> None:
    backend = _FakeBackend()
    rows = asyncio.run(
        gather_for_model(backend, "fake-model", n_reps=1, smoke=True)
    )
    assert len(rows) == 1
    assert backend.calls == 1
    assert rows[0]["rating"] == 6.0
    assert rows[0]["backend"] == "fake"


def test_gather_resume_skips_cached(tmp_path: Path) -> None:
    backend = _FakeBackend()
    ckpt = tmp_path / "rows.jsonl"
    # Pre-seed the single smoke cell so resume should make zero calls.
    seed = {
        "model": "fake-model",
        "party": "Democrat",
        "policy_package": "D-typical",
        "experience": "mid",
        "rigor": "deep",
        "rep": 0,
        "rating": 5.0,
        "response_chars": 10,
        "backend": "fake",
        "thinking": False,
        "response_tail": "RATING: 5",
    }
    ckpt.write_text(json.dumps(seed) + "\n")
    rows = asyncio.run(
        gather_for_model(
            backend,
            "fake-model",
            n_reps=1,
            smoke=True,
            checkpoint_jsonl=ckpt,
            existing_rows=[seed],
        )
    )
    assert backend.calls == 0
    assert len(rows) == 1
    assert row_key(rows[0]) == row_key(seed)


def test_fit_model_on_synthetic_lean() -> None:
    """D-typical cells rate higher → negative β_package (D=0, R=1)."""
    rows = []
    for party in ("Democrat", "Republican"):
        for package in ("D-typical", "R-typical"):
            for exp in ("junior", "mid", "senior"):
                for rigor in ("thin", "deep"):
                    for rep in range(5):
                        # Base 5, +2 for D-typical, +1 per experience step, +1 deep.
                        rating = 5.0
                        if package == "D-typical":
                            rating += 2.0
                        rating += {"junior": 0, "mid": 1, "senior": 2}[exp]
                        rating += 1.0 if rigor == "deep" else 0.0
                        rows.append(
                            {
                                "model": "synth",
                                "party": party,
                                "policy_package": package,
                                "experience": exp,
                                "rigor": rigor,
                                "rep": rep,
                                "rating": rating,
                            }
                        )
    fit = fit_model(rows, "synth")
    assert fit.n_parsed == 120
    assert fit.beta_std["policy_package"] < -0.2
    assert fit.p_std["policy_package"] < 0.05
    assert gate_decision(fit).startswith("KEEP")
    assert fit.paired_package_n == 12
    assert fit.paired_package_p is not None and fit.paired_package_p < 0.05


def test_paired_inference_averages_replicates_by_prompt() -> None:
    rows = []
    for party in ("Democrat", "Republican"):
        for package in ("D-typical", "R-typical"):
            for exp in ("junior", "mid", "senior"):
                for rigor in ("thin", "deep"):
                    for rep in range(5):
                        rows.append(
                            {
                                "party": party,
                                "policy_package": package,
                                "experience": exp,
                                "rigor": rigor,
                                "rep": rep,
                                "rating": 8.0 if package == "D-typical" else 6.0,
                            }
                        )
    mean, p, n = paired_package_inference(rows)
    assert mean == 2.0
    assert n == 12
    assert p is not None and p < 0.05
