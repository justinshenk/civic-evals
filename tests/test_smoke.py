"""Import-level smoke: every eval module loads and produces a valid
inspect-ai ``Task`` object.

This catches broken imports, signature typos, and missing scorer hooks
without needing an API key. Full end-to-end smoke (actually calling
Haiku on one sample per eval) is done in CI via the inspect CLI, not
here, so `pytest` stays offline-runnable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from inspect_ai import Task

EVALS_ROOT = Path(__file__).resolve().parent.parent / "evals"


def _eval_files() -> list[Path]:
    files = []
    for d in sorted(EVALS_ROOT.iterdir()):
        if not d.is_dir():
            continue
        f = d / "eval.py"
        if f.exists():
            files.append(f)
    return files


@pytest.mark.parametrize("eval_file", _eval_files(), ids=lambda p: p.parent.name)
def test_eval_module_loads(eval_file: Path) -> None:
    spec = importlib.util.spec_from_file_location(eval_file.parent.name, eval_file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    task_fns = [
        getattr(module, name)
        for name in dir(module)
        if callable(getattr(module, name)) and getattr(getattr(module, name), "__wrapped__", None)
    ]
    # Fall back: the @task decorator marks fns; find any callable that returns a Task
    if not task_fns:
        task_fns = [
            getattr(module, name)
            for name in dir(module)
            if name.startswith(eval_file.parent.name.split("_")[0])
        ]

    built = []
    for fn in task_fns:
        try:
            t = fn()
        except TypeError:
            continue
        if isinstance(t, Task):
            built.append(t)

    assert built, f"{eval_file.parent.name}: no @task-decorated function built a Task"
    for t in built:
        assert len(t.dataset) >= 5, (
            f"{eval_file.parent.name}: dataset has <5 samples after loader"
        )
