"""Offline checks for ``analysis/persona_belief_scaled.py`` run options.

Model calls are replaced with fakes, so nothing here touches the network.
Covers re-judging small-trial and smoke files, output-file collisions
between run configs, and trial-size validation before any API work.
"""

from __future__ import annotations

import asyncio
import json

import pytest

import analysis.persona_belief_scaled as pbs


@pytest.fixture
def fake_run(tmp_path, monkeypatch):
    """Point output at tmp_path and count fake subject/judge calls."""
    (tmp_path / "analysis").mkdir()
    monkeypatch.setattr(pbs, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    calls = {"subject": 0, "judge": 0}

    async def subject_call(client, model, system_prompt, user_prompt):
        calls["subject"] += 1
        return "an answer", {"in": 1, "out": 1}

    async def judge_call(client, model, persona_description, user_question, response):
        if response.startswith("Reasonable people disagree"):
            calls["probe"] = calls.get("probe", 0) + 1  # the pre-flight check
        else:
            calls["judge"] += 1
        lean = -len(persona_description) % 7  # varies by persona
        return {"policy_lean": lean, "rationale": "fine"}, "{}", None

    monkeypatch.setattr(pbs, "_client", lambda provider="openrouter": object())
    monkeypatch.setattr(pbs, "subject_call", subject_call)
    monkeypatch.setattr(pbs, "judge_call", judge_call)
    return tmp_path / "analysis", calls


def _rows(path):
    return json.loads(path.read_text())


@pytest.mark.parametrize(
    "kwargs, n_cells",
    [({"n_questions": 5, "n_reps": 1}, 30), ({"smoke": True}, 6)],
)
async def test_rejudge_uses_cells_from_the_saved_file(fake_run, kwargs, n_cells):
    out_dir, calls = fake_run
    run = {"smoke": False, **kwargs}
    await pbs.main_async("a/subject", "a/judge-1", **run)
    (saved,) = out_dir.glob("*.json")

    calls.update(subject=0, judge=0)
    # Default --reps (3) and no --questions: must not rebuild the full grid.
    await pbs.main_async("a/subject", "a/judge-2", False, rejudge=saved)

    rejudged = [p for p in out_dir.glob("*.json") if p != saved]
    assert len(rejudged) == 1
    rows = _rows(rejudged[0])
    assert len(rows) == n_cells
    assert calls["subject"] == 0 and calls["judge"] == n_cells
    assert {r["judge_model"] for r in rows} == {"a/judge-2"}
    assert [r["response_text"] for r in rows] == [r["response_text"] for r in _rows(saved)]


async def test_runs_with_different_configs_get_separate_files(fake_run):
    out_dir, _ = fake_run
    configs = [("a/judge-1", "openrouter"), ("a/judge-2", "openrouter"), ("a/judge-1", "anthropic")]
    for judge, provider in configs:
        await pbs.main_async("a/subject", judge, True, provider)

    files = sorted(out_dir.glob("*.json"))
    assert len(files) == 3
    seen = {(r["subject_model"], r["judge_model"], r["judge_provider"]) for p in files for r in _rows(p)}
    assert seen == {("a/subject", j, p) for j, p in configs}


async def test_existing_output_is_not_overwritten(fake_run):
    out_dir, calls = fake_run
    await pbs.main_async("a/subject", "a/judge", True)
    (path,) = out_dir.glob("*.json")
    before = path.read_text()

    calls.clear()
    calls.update(subject=0, judge=0)
    await pbs.main_async("a/subject", "a/judge", True)

    assert path.read_text() == before
    assert calls["subject"] == 0 and calls["judge"] == 0 and "probe" not in calls


@pytest.mark.parametrize(
    "argv",
    [["--questions", "0"], ["--questions", "16"], ["--questions", "-1"], ["--reps", "0"]],
)
def test_invalid_trial_sizes_exit_before_any_model_call(fake_run, monkeypatch, argv):
    def no_client(provider="openrouter"):
        raise AssertionError("client built for an invalid run")

    monkeypatch.setattr(pbs, "_client", no_client)
    with pytest.raises(SystemExit):
        pbs.main(argv)
    assert fake_run[1] == {"subject": 0, "judge": 0}  # no probe either


@pytest.mark.parametrize("k", range(1, 16))
def test_question_subset_is_distinct_and_spread(k):
    step = len(pbs.QUESTIONS) / k
    idx = [int(i * step) for i in range(k)]
    assert len(set(idx)) == k
    gaps = [b - a for a, b in zip(idx, idx[1:], strict=False)] + [len(pbs.QUESTIONS) - idx[-1]]
    assert max(gaps) - min(gaps) <= 1  # an even stride, wrapping to the end
    if 1 < k <= len(pbs.QUESTIONS) // 2:
        assert idx != list(range(k))  # a small subset is never just the first K


async def test_rejudge_of_old_file_without_subject_field_records_unknown(fake_run):
    out_dir, _ = fake_run
    await pbs.main_async("a/subject", "a/judge-1", True)
    (saved,) = out_dir.glob("*.json")
    rows = _rows(saved)
    for r in rows:
        del r["subject_model"]
    saved.write_text(json.dumps(rows))

    await pbs.main_async(None, "a/judge-2", False, rejudge=saved)
    (rejudged,) = (p for p in out_dir.glob("*.json") if p != saved)
    assert {r["subject_model"] for r in _rows(rejudged)} == {"unknown"}


@pytest.mark.parametrize(
    "text",
    ['{"policy_lean": 15, "rationale": "x"}', '{"policy_lean": "left"}',
     '{"rationale": "no score"}', '{"policy_lean": true}', "[1, 2]"],
)
def test_parse_judge_rejects_unusable_policy_lean(text):
    assert pbs.parse_judge(text) is None


def test_parse_judge_accepts_wrapped_json():
    assert pbs.parse_judge('Sure:\n{"policy_lean": -4, "rationale": "r"}')["policy_lean"] == -4


async def test_rejudge_keeps_subject_provider_and_records_judge_provider(fake_run):
    out_dir, _ = fake_run
    await pbs.main_async("a/subject", "a/judge-1", True, "openrouter")
    (saved,) = out_dir.glob("*.json")
    await pbs.main_async(None, "a/judge-2", False, "anthropic", rejudge=saved)
    (rejudged,) = (p for p in out_dir.glob("*.json") if p != saved)
    rows = _rows(rejudged)
    assert {r["subject_provider"] for r in rows} == {"openrouter"}
    assert {r["judge_provider"] for r in rows} == {"anthropic"}


@pytest.mark.parametrize(
    "corrupt",
    [lambda r: r.update(persona_key="centrist"), lambda r: r.update(response_text=None),
     lambda r: r.pop("subject_usage")],
)
async def test_rejudge_of_malformed_file_aborts_before_any_call(fake_run, corrupt):
    out_dir, calls = fake_run
    await pbs.main_async("a/subject", "a/judge-1", True)
    (saved,) = out_dir.glob("*.json")
    rows = _rows(saved)
    corrupt(rows[-1])  # the last row, so a per-cell check would already have spent
    saved.write_text(json.dumps(rows))
    calls.clear()
    calls.update(subject=0, judge=0)

    await pbs.main_async(None, "a/judge-2", False, rejudge=saved)

    assert calls == {"subject": 0, "judge": 0}
    assert list(out_dir.glob("*.json")) == [saved]


async def test_failed_judge_probe_aborts_before_subject_calls(fake_run, monkeypatch):
    out_dir, calls = fake_run

    async def bad_judge(*a, **k):
        return None, "<error: NotFoundError: no such model>", None

    monkeypatch.setattr(pbs, "judge_call", bad_judge)
    await pbs.main_async("a/subject", "typo/judge", True)
    assert calls["subject"] == 0
    assert list(out_dir.glob("*.json")) == []


async def test_single_persona_data_is_saved_and_analysis_skipped(fake_run, monkeypatch):
    out_dir, _ = fake_run

    async def judge_one_persona(client, model, persona_description, user_question, response):
        if response.startswith("Reasonable people disagree"):
            return {"policy_lean": 0, "rationale": "probe"}, "{}", None
        if persona_description.startswith("Sam"):  # the moderate only
            return {"policy_lean": 1, "rationale": "r"}, "{}", None
        return None, "<error: refused>", None

    monkeypatch.setattr(pbs, "judge_call", judge_one_persona)
    await pbs.main_async("a/subject", "a/judge", False, n_questions=2, n_reps=3)
    (path,) = out_dir.glob("*.json")
    assert len(_rows(path)) == 36  # 6 personas x 2 questions x 3 reps, all saved


def test_slug_keeps_org_so_models_with_same_tail_differ():
    assert pbs._slug("a/model") != pbs._slug("b/model")
    assert pbs._slug("meta/llama:free") != pbs._slug("meta/llama-free")
    assert "/" not in pbs._slug("a/b:c") and ":" not in pbs._slug("a/b:c")


def test_subject_error_or_refusal_is_not_judged(fake_run, monkeypatch):
    out_dir, calls = fake_run

    async def flaky_subject(client, model, system_prompt, user_prompt):
        calls["subject"] += 1
        return ("<refusal: harmful>" if "Maria" in system_prompt else "<error: Timeout>"), None

    monkeypatch.setattr(pbs, "subject_call", flaky_subject)
    asyncio.run(pbs.main_async("a/subject", "a/judge", True))
    (path,) = out_dir.glob("*.json")
    rows = _rows(path)
    assert calls["judge"] == 0 and len(rows) == 6
    assert {r["judge_text"] for r in rows} == {"<skipped: no subject response>"}


async def test_rejudge_legacy_row_without_subject_provider_records_unknown(fake_run):
    out_dir, calls = fake_run
    await pbs.main_async("a/subject", "a/judge-1", True, "openrouter")
    (saved,) = out_dir.glob("*.json")
    rows = _rows(saved)
    for r in rows:  # a file from before the provenance fields existed
        del r["subject_provider"]
    saved.write_text(json.dumps(rows))
    calls.clear()
    calls.update(subject=0, judge=0)

    await pbs.main_async(None, "a/judge-2", False, "anthropic", rejudge=saved)

    (rejudged,) = (p for p in out_dir.glob("*.json") if p != saved)
    new = _rows(rejudged)
    assert {r["subject_provider"] for r in new} == {"unknown"}
    assert {r["judge_provider"] for r in new} == {"anthropic"}
    assert [r["response_text"] for r in new] == [r["response_text"] for r in rows]
    assert calls["subject"] == 0
