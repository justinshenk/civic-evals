"""The explicit offline report path must never initialize an API judge."""

import importlib
import json
import sys

import pandas as pd


def test_skip_staleness_judge_writes_scores_without_api_calls(monkeypatch, tmp_path):
    module = importlib.import_module("analysis.rollup")
    row = {"eval": "example", "provider": "test/model", "scorer": "rubric_judge", "score": 0.75}
    monkeypatch.setattr(module, "rollup", lambda _: pd.DataFrame([row]))
    for name in (
        "collect_eval_meta", "calibration_stats", "collect_external_baselines",
        "collect_failures", "_collect_usage", "collect_cell_stats",
    ):
        monkeypatch.setattr(module, name, lambda _: [])
    monkeypatch.setattr(module, "collect_bias", lambda: [])

    def forbidden():
        raise AssertionError("Offline reporting must not initialize staleness judging")

    monkeypatch.setattr(module, "_staleness_helpers", forbidden)
    output = tmp_path / "rollup.json"
    monkeypatch.setattr(sys, "argv", [
        "rollup.py", str(tmp_path), "--skip-staleness-judge", "--format", "json", "-o", str(output),
    ])
    assert module.main() == 0
    assert json.loads(output.read_text())["rows"] == [row]
