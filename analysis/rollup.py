"""Walk ``logs/*.eval`` and produce a long-form dataframe.

One row per ``(eval, task_id, persona, provider, scorer)`` tuple. All
downstream reporting (per-persona accuracy, consistency heatmaps,
symmetry checks across paired tasks) operates on this single frame, so
adding a new scorer or persona doesn't require touching analysis code.

Usage::

    python analysis/rollup.py logs/ > rollup.parquet
    python analysis/rollup.py logs/ --format csv > rollup.csv
"""

from __future__ import annotations

import argparse
import json as _json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from inspect_ai.log import list_eval_logs, read_eval_log

REPO_ROOT = Path(__file__).resolve().parent.parent

# Match inspect-ai's behavior: load .env from the repo root so the staleness
# judge can find ANTHROPIC_API_KEY without manual exports. Best-effort —
# missing dotenv or missing file is not an error.
try:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env", override=False)
except ImportError:
    pass


def rollup(log_dir: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for log_file in list_eval_logs(str(log_dir)):
        log = read_eval_log(log_file)
        eval_name = log.eval.task
        provider = getattr(log.eval, "model", "") or ""
        for sample in log.samples or []:
            meta = sample.metadata or {}
            persona = meta.get("persona")
            persona_role = _persona_label(persona)
            persona_attrs = persona if isinstance(persona, dict) else None
            completion = _truncate(_completion_text(sample), 600)
            scores = sample.scores or {}
            for scorer_name, score in scores.items():
                score_meta = score.metadata or {}
                rows.append(
                    {
                        "eval": eval_name,
                        "task_id": sample.id,
                        "provider": provider,
                        "persona": persona_role,
                        "persona_attrs": persona_attrs,
                        "domain": meta.get("domain"),
                        "subdomain": meta.get("subdomain"),
                        "difficulty": meta.get("difficulty"),
                        "tags": ",".join(meta.get("tags") or []),
                        "scorer": scorer_name,
                        "score": _as_float(score.value),
                        "explanation": score.explanation or "",
                        "completion": completion,
                        "sub_scores": score_meta.get("sub_scores"),
                        "score_metadata": _scorer_diagnostics(score_meta),
                    }
                )
    return pd.DataFrame(rows)


# Whitelist of scorer-metadata keys the site needs (e.g. fermi range bar).
# Pass-through would bloat the rollup; named keys keep the contract explicit.
_DIAG_KEYS = ("truth", "estimate", "ci_low", "ci_high", "parse_success", "refused")


# Per-difficulty score thresholds for "this should worry you" surfacing.
# Easy questions (binary facts, single-statute lookups) should be near-perfect:
# a 0.98 mean still hides confidently-wrong answers and we want to see them.
# Medium tasks have more legitimate room for partial credit. Hard tasks are
# excluded — the goal here is alarming-on-easy, not a generic underperformance
# report. Tune by editing this dict; the CLI and site update from one source.
_FAILURE_THRESHOLDS: dict[str, float] = {"easy": 0.9, "medium": 0.7}


def _scorer_diagnostics(score_meta: dict[str, Any]) -> dict[str, Any] | None:
    out = {k: score_meta[k] for k in _DIAG_KEYS if k in score_meta}
    return out or None


def _completion_text(sample: Any) -> str:
    output = getattr(sample, "output", None)
    if output is None:
        return ""
    text = getattr(output, "completion", None)
    return text if isinstance(text, str) else ""


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def collect_eval_meta(evals_dir: Path) -> list[dict[str, Any]]:
    """Walk ``evals_dir/*`` and produce one metadata blob per eval.

    Pulls description from the README (first prose paragraph after the
    H1) and computes task counts, difficulty distribution, subdomains,
    and persona usage from ``tasks.jsonl`` directly — so metadata is
    always in sync with the source of truth.
    """
    out: list[dict[str, Any]] = []
    if not evals_dir.is_dir():
        return out
    from p3.schemas import load_tasks  # local import to avoid hard dep at module load

    for d in sorted(evals_dir.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        tasks_path = d / "tasks.jsonl"
        if not tasks_path.exists():
            continue
        try:
            tasks = load_tasks(tasks_path)
        except Exception:
            continue

        difficulties = Counter(t.metadata.difficulty for t in tasks)
        subdomains = sorted({t.subdomain for t in tasks})
        personas = sorted(
            {(t.persona.name if t.persona and t.persona.name else "none") for t in tasks}
        )
        scorer_kinds = sorted(
            {("rubric" if t.rubric else "target") for t in tasks}
        )
        # Per-eval track is the dominant value across its tasks. Mixed
        # evals (some factual, some interpretive) are uncommon but
        # represented faithfully — site can show the breakdown.
        tracks = Counter(t.metadata.track for t in tasks)
        if not tracks or all(k is None for k in tracks):
            track = None
        elif len(tracks) == 1:
            track = next(iter(tracks))
        else:
            track = "mixed"

        out.append(
            {
                "name": d.name,
                "description": _readme_summary(d / "README.md"),
                "task_count": len(tasks),
                "difficulty": dict(sorted(difficulties.items())),
                "subdomains": subdomains,
                "personas_used": personas,
                "scorer_kinds": scorer_kinds,
                "track": track,
                "readme_url": (
                    f"https://github.com/justinshenk/civic-evals/blob/main/evals/{d.name}/README.md"
                ),
                "tasks": [_task_summary(t) for t in tasks],
            }
        )
    return out


_REFUSAL_RE = re.compile(
    r"refusal_expected\s*=\s*(refuse|answer|hedge)\b", re.IGNORECASE
)


def _task_summary(task: Any) -> dict[str, Any]:
    """Compact per-task blob for rendering in the site.

    Truncates rubric to a one-liner so the JSON payload doesn't balloon
    — the full rubric is in tasks.jsonl on GitHub for anyone who wants it.
    """
    extras = task.metadata.extras or {}
    notes = task.metadata.notes or ""
    refusal_expected = extras.get("refusal_expected")
    if not refusal_expected:
        m = _REFUSAL_RE.search(notes)
        if m:
            refusal_expected = m.group(1).lower()

    rubric_snippet = None
    if task.rubric:
        rubric_snippet = task.rubric.split(".")[0].strip()
        if len(rubric_snippet) > 220:
            rubric_snippet = rubric_snippet[:217] + "…"

    return {
        "id": task.id,
        "input": task.input,
        "subdomain": task.subdomain,
        "difficulty": task.metadata.difficulty,
        "tags": task.metadata.tags,
        "persona": (task.persona.name if task.persona and task.persona.name else None),
        "scorer_kind": "rubric" if task.rubric else "target",
        "target": task.target,
        "rubric_snippet": rubric_snippet,
        "refusal_expected": refusal_expected,
        "source": task.metadata.source,
        "last_verified": task.metadata.last_verified,
        "track": task.metadata.track,
    }


_HEADING_RE = re.compile(r"^#+\s")


_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)")


def _readme_summary(readme: Path) -> str:
    """Return the first non-heading prose paragraph after the H1.

    If the paragraph ends with a colon and is followed by a bullet list
    (a common pattern: "Tasks split into:" + bullets), include the first
    three bullet labels so the description doesn't trail off mid-thought.
    """
    if not readme.exists():
        return ""
    lines = readme.read_text().splitlines()
    i = 0
    while i < len(lines) and not lines[i].startswith("# "):
        i += 1
    i += 1
    paragraph: list[str] = []
    started = False
    while i < len(lines):
        line = lines[i].rstrip()
        if _HEADING_RE.match(line):
            break
        if not line:
            if started:
                break
        else:
            started = True
            paragraph.append(line)
        i += 1
    text = _strip_md(" ".join(paragraph).strip())

    if text.endswith(":"):
        # Skip blank lines
        while i < len(lines) and not lines[i].strip():
            i += 1
        bullets: list[str] = []
        while i < len(lines):
            m = _BULLET_RE.match(lines[i])
            if not m or len(bullets) >= 3:
                break
            bullets.append(_strip_md(m.group(1)))
            i += 1
        if bullets:
            text = text[:-1] + ": " + "; ".join(bullets) + "."
    return text


def _strip_md(s: str) -> str:
    """Strip the lightweight markdown bold/em that appears in bullet labels."""
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*]+)\*", r"\1", s)
    return s.strip()


def _persona_label(persona: Any) -> str:
    if not persona:
        return "none"
    if isinstance(persona, dict):
        return persona.get("role", "custom")
    return str(persona)


# Catalog of baselines we pull from inspect_evals as comparison points.
# Keep concise — this is a label, not a full re-derivation. The actual
# data is whatever rows show up under these eval names in the rollup.
_BASELINE_CATALOG: dict[str, dict[str, str]] = {
    "truthfulqa": {
        "title": "TruthfulQA",
        "description": (
            "Measures whether a model produces falsehoods on questions some "
            "humans get wrong. Lin et al., 2022. Comparison axis for "
            "election_integrity."
        ),
        "arxiv": "https://arxiv.org/abs/2109.07958",
        "source": "UKGovernmentBEIS/inspect_evals",
    },
    "simpleqa": {
        "title": "SimpleQA",
        "description": (
            "Single-fact recall benchmark from OpenAI; tests verifiable "
            "factual answers. Comparison axis for voting_access exact-fact "
            "subset."
        ),
        "arxiv": "https://openai.com/index/introducing-simpleqa-a-new-benchmark/",
        "source": "UKGovernmentBEIS/inspect_evals",
    },
}


def collect_external_baselines(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Summary entry for each external (inspect_evals) baseline observed.

    The point of these isn't to replicate the published numbers — we run
    them with --limit so they're rough comparison axes only. The site
    treats them as context: "civic eval scored X; same model on
    TruthfulQA scored Y, so the civic gap is real and not just a
    capability ceiling."
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for eval_name in df["eval"].dropna().unique():
        if not eval_name.startswith("inspect_evals/"):
            continue
        short = eval_name.split("/", 1)[1]
        if short in seen:
            continue
        seen.add(short)
        meta = _BASELINE_CATALOG.get(short, {
            "title": short,
            "description": "External baseline pulled from inspect_evals.",
            "source": "UKGovernmentBEIS/inspect_evals",
        })
        rows = df[df["eval"] == eval_name]
        out.append(
            {
                "name": eval_name,
                "short_name": short,
                "title": meta["title"],
                "description": meta["description"],
                "arxiv": meta.get("arxiv"),
                "source": meta["source"],
                "providers": sorted(rows["provider"].dropna().unique().tolist()),
                "n_rows": int(len(rows)),
            }
        )
    return out


def _collect_usage(log_dir: Path) -> list[dict[str, Any]]:
    """Token-usage and cost rows per (eval, model). Same script-vs-module
    import dance as ``_staleness_helpers``.

    Failures here (missing inspect-ai, malformed logs) shouldn't block a
    rollup; degrade to an empty list and let the caller render an empty
    usage block.
    """
    try:
        from analysis.usage import collect_usage
    except ModuleNotFoundError:
        try:
            from usage import collect_usage  # type: ignore[import-not-found, no-redef]
        except ModuleNotFoundError:
            return []
    try:
        return collect_usage(log_dir)
    except Exception as e:  # malformed log, etc. — don't kill the rollup
        import logging

        logging.getLogger(__name__).warning("usage collection failed: %s", e)
        return []


def _staleness_helpers() -> tuple[Any, Any]:
    """Local import that works both as a script and as a module.

    ``python analysis/rollup.py`` puts ``analysis/`` on ``sys.path`` so
    ``staleness_judge`` is importable as a top-level module. ``from
    analysis.rollup import …`` (test invocation) puts the repo root on
    path, so the ``analysis.staleness_judge`` form resolves. Try the
    package-qualified form first; fall back to the sibling-script form.
    """
    try:
        from analysis.staleness_judge import is_search_eval, judge_failures
    except ModuleNotFoundError:
        from staleness_judge import (  # type: ignore[import-not-found, no-redef]
            is_search_eval,
            judge_failures,
        )
    return is_search_eval, judge_failures


def collect_bias(rows_path: Path | None = None) -> list[dict[str, Any]]:
    """Re-fit the school-board candidate factorial from the raw rows.

    The bias measurement (Eric's experiment, May 2026) lives in
    ``analysis/multi_model_rows.json`` as a flat list of 720 ratings.
    Re-fitting at rollup time means the headline yrs-per-package
    number on the site is *always* derivable from the raw data — no
    hand-typed numbers in markdown to drift out of sync.

    Returns one record per model with:

    - ``model`` — provider/short id (e.g. ``anthropic/claude-haiku-4.5``)
    - ``years_per_package`` — the headline metric. Positive = D-typical
      platform rated higher than R-typical (controlling for label,
      experience, and rigor), expressed as years of equivalent
      experience the R-platform candidate "loses".
    - ``years_per_party`` — same metric for party label alone. Usually
      tiny / non-significant; included for completeness.
    - ``beta_package_zz`` / ``p_package`` / ``r2`` — standardized
      coefficient, two-sided p-value, and R² from the canonical
      z-standardized OLS fit.
    - ``rating_mean`` / ``rating_sd`` / ``n_parsed`` / ``n_total`` —
      sanity / coverage stats per model.

    Returns ``[]`` when the raw rows file is missing — keeps the rollup
    resilient on forks that don't have OpenRouter access.
    """
    rows_path = rows_path or REPO_ROOT / "analysis" / "multi_model_rows.json"
    if not rows_path.exists():
        return []
    try:
        raw = _json.loads(rows_path.read_text())
    except Exception:
        return []
    if not isinstance(raw, list) or not raw:
        return []

    # Local import. Two paths because rollup.py runs both as a script
    # (`python analysis/rollup.py`, in which case ``analysis/`` is on
    # sys.path but not the repo root) and as a module (`from
    # analysis.rollup import ...`, in which case the package import
    # works). Same pattern as ``_collect_usage`` above.
    try:
        from analysis.multi_model_bias import fit_model
    except ImportError:
        try:
            from multi_model_bias import fit_model  # type: ignore[import-not-found, no-redef]
        except Exception:
            return []
    except Exception:
        return []

    by_model: dict[str, list[dict[str, Any]]] = {}
    for r in raw:
        model = r.get("model")
        if not model:
            continue
        by_model.setdefault(model, []).append(r)

    out: list[dict[str, Any]] = []
    for model, model_rows in sorted(by_model.items()):
        try:
            fit = fit_model(model_rows, model)
        except Exception:
            continue
        out.append(
            {
                "model": model,
                "years_per_package": fit.years_per_package,
                "years_per_party": fit.years_per_party,
                "beta_package_zz": fit.beta_std.get("policy_package"),
                "p_package": fit.p_std.get("policy_package"),
                "r2": fit.r2_std,
                "rating_mean": fit.rating_mean,
                "rating_sd": fit.rating_sd,
                "n_parsed": fit.n_parsed,
                "n_total": fit.n_total,
            }
        )
    # Sort by magnitude of policy bias desc — the site's bar chart
    # reads from this order.
    out.sort(
        key=lambda x: -abs(x["years_per_package"] or 0.0),
    )
    return out


def collect_failures(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Per-row entries where ``score`` is below the difficulty's threshold.

    A high mean (e.g. 0.98 on easy binary-fact tasks) can hide a small
    population of confidently-wrong answers. The aggregate doesn't surface
    them; this list does. Sorted so the most alarming case (lowest score on
    the easiest difficulty) appears first.

    Skips rows missing ``score`` or ``difficulty`` — neither is actionable
    without both. ``appropriate_refusal`` rows scored 0.5 because no
    ``refusal_expected`` was set are not failures by design; the threshold
    keeps them out without special-casing.
    """
    if df.empty:
        return []

    is_search, _ = _staleness_helpers()

    out: list[dict[str, Any]] = []
    # easy=0, medium=1, others=2 — used purely to sort easy failures first.
    rank = {"easy": 0, "medium": 1}
    for _, row in df.iterrows():
        difficulty = row.get("difficulty")
        score = row.get("score")
        if difficulty not in _FAILURE_THRESHOLDS or score is None:
            continue
        if not isinstance(score, (int, float)) or math.isnan(float(score)):
            continue
        if float(score) >= _FAILURE_THRESHOLDS[difficulty]:
            continue
        # appropriate_refusal returns 0.5 (neutral) when the task has no
        # ``refusal_expected`` set — that's "we didn't ask," not a failure.
        # See src/p3/scorers/refusal.py:76-77. Filter on the scorer's own
        # explanation rather than threading a new metadata field.
        if (
            row.get("scorer") == "appropriate_refusal"
            and "no refusal_expected set" in str(row.get("explanation") or "")
        ):
            continue
        sub = row.get("sub_scores")
        completion = row.get("completion") or ""
        eval_name = row.get("eval")
        meta = row.get("score_metadata")
        # Surface the scorer's own ``refused`` marker as a flat field so the
        # site can render a "refusal-shaped" indicator on the failure card.
        # The fermi scorer sets this when the model declined to commit to a
        # number (parse failure or zero-point/zero-width interval against
        # non-zero truth) — distinct from the rollup-time staleness verdict.
        refused = bool(meta.get("refused")) if isinstance(meta, dict) else None
        out.append(
            {
                "eval": eval_name,
                "task_id": row.get("task_id"),
                "difficulty": difficulty,
                "persona": row.get("persona"),
                "provider": row.get("provider"),
                "scorer": row.get("scorer"),
                "score": float(score),
                "threshold": _FAILURE_THRESHOLDS[difficulty],
                "explanation": row.get("explanation") or "",
                "completion": completion,
                "sub_scores": sub if isinstance(sub, dict) else None,
                "refused": refused,
                # Verdict fields are populated by ``judge_failures`` after
                # collection. ``None`` here means "not yet judged"; the judge
                # leaves it ``None`` for search-enabled evals or when no API
                # key is set, so the site renders that as "not applicable."
                "acknowledged_staleness": None,
                "staleness_kind": None,
                "staleness_evidence": None,
            }
        )
    out.sort(key=lambda r: (rank.get(r["difficulty"], 99), r["score"]))
    return out


def failure_summary(failures: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate counts for the staleness-acknowledgement check.

    Splits failures into the populations the reviewer cared about: those
    that arrived with epistemic-humility hedging (model knows it might be
    stale or pointed at an authoritative source) vs those that did not.
    Search-enabled evals are excluded — their failures should be measured
    by ``citation_verifiability``, not by hedge phrases.

    Returns one row per eval and a ``"all"`` rollup row, so the site can
    show both per-eval and overall numbers without recomputation.
    """
    rows: dict[str, dict[str, int]] = {"all": {"n": 0, "ack": 0, "no_ack": 0}}
    for f in failures:
        ack = f.get("acknowledged_staleness")
        if ack is None:  # search-enabled; not in the population
            continue
        eval_name = f.get("eval") or "?"
        for bucket in (eval_name, "all"):
            rows.setdefault(bucket, {"n": 0, "ack": 0, "no_ack": 0})
            rows[bucket]["n"] += 1
            rows[bucket]["ack" if ack else "no_ack"] += 1

    out: list[dict[str, Any]] = []
    for name, c in sorted(rows.items()):
        n = c["n"]
        out.append({
            "eval": name,
            "n_failures": n,
            "n_acknowledged": c["ack"],
            "n_unacknowledged": c["no_ack"],
            "ack_rate": (c["ack"] / n) if n else None,
        })
    return {"by_eval": out}


def calibration_stats(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Per (eval, provider) calibration AUROC for fermi-style scorers.

    Frames calibration as: does the model give narrower CIs on tasks it
    gets right? AUROC over (confidence = -ci_width_rel, correct =
    point_score >= 0.9). 0.5 = chance, 1.0 = perfect rank ordering, < 0.5
    = anti-calibrated (narrower on the things it gets wrong).

    The metric closely follows the calibration AUROC reported by Vashurin
    et al. (TACL 2025, "Benchmarking UQ Methods for LLMs with
    LM-Polygraph") — there over an LLM's stated or derived per-claim
    confidence; here over the explicit CI width the eval already asks
    for. Only computed when the row's scorer surfaced both ``ci_width_rel``
    in sub_scores and ``point_score`` (the fermi scorer's contract).
    """
    out: list[dict[str, Any]] = []
    fermi_rows = df[df["scorer"] == "fermi_calibration"]
    if fermi_rows.empty:
        return out

    for (eval_name, provider), group in fermi_rows.groupby(["eval", "provider"]):
        scores: list[float] = []
        labels: list[int] = []
        n_correct = 0
        for _, row in group.iterrows():
            width_rel, point = _calibration_inputs(row)
            if width_rel is None or point is None:
                continue
            # Confidence = narrowness; AUROC is rank-based so any
            # monotone-decreasing transform of width_rel works.
            scores.append(-width_rel)
            correct = 1 if point >= 0.9 else 0
            labels.append(correct)
            n_correct += correct

        au = _auroc(scores, labels)
        out.append(
            {
                "eval": eval_name,
                "provider": provider,
                "metric": "calibration_auroc",
                "value": au,
                "n": len(scores),
                "n_correct": n_correct,
                "explanation": (
                    "AUROC of (1/CI-width) vs (point_score ≥ 0.9). The 0.9 "
                    "threshold covers the full ±10% credit zone plus the "
                    "tightest portion of the linear-decay range (~±19% of "
                    "truth). Higher = narrower CIs on questions the model "
                    "gets right."
                ),
            }
        )
    return out


def _calibration_inputs(row: Any) -> tuple[float | None, float | None]:
    """Extract (ci_width_rel, point_score) from a fermi row.

    Robust to scorer-version drift: prefers sub_scores fields
    (``ci_width_rel``, ``point_score``) when present, falls back to
    deriving them from ``score_metadata`` (truth/estimate/ci_low/ci_high)
    so historical logs scored under earlier formulas still contribute.
    """
    sub = row.get("sub_scores") or {}
    sm = row.get("score_metadata") or {}

    width_rel: float | None = None
    if isinstance(sub.get("ci_width_rel"), (int, float)):
        width_rel = float(sub["ci_width_rel"])
    else:
        truth = sm.get("truth")
        lo, hi = sm.get("ci_low"), sm.get("ci_high")
        if all(isinstance(x, (int, float)) for x in (truth, lo, hi)):
            denom = max(abs(float(truth)), 1.0)
            width_rel = max(0.0, float(hi) - float(lo)) / denom

    point: float | None = None
    if isinstance(sub.get("point_score"), (int, float)):
        point = float(sub["point_score"])
    else:
        truth = sm.get("truth")
        est = sm.get("estimate")
        if all(isinstance(x, (int, float)) for x in (truth, est)):
            point = _reconstruct_point_score(float(truth), float(est))

    return width_rel, point


def _reconstruct_point_score(truth: float, estimate: float) -> float:
    """Re-derive ``point_score`` from raw (truth, estimate) for historical logs.

    Mirrors ``p3.scorers.fermi._point_score``: 1.0 within ±10%, linear decay to
    0 at ±100%, *exponential* decay past that with half-life one factor of 2.
    The earlier implementation cut off at the linear branch and clamped to 0
    for any rel > 1.0, which made the AUROC reconstruction disagree with the
    live scorer for very-wrong estimates (see fc-018: estimate=0 vs truth=226
    is rel ≈ 1.0, dead on the boundary; rel just above gave 0 here but ~0.4
    in the live scorer).
    """
    if truth == 0:
        return 1.0 if estimate == 0 else 0.0
    rel = abs(estimate - truth) / abs(truth)
    if rel <= 0.10:
        return 1.0
    if rel <= 1.0:
        return 1.0 - (rel - 0.10) / 0.90
    return max(0.0, math.exp(-(rel - 1.0)))


def _auroc(scores: list[float], labels: list[int]) -> float | None:
    """Mann-Whitney U / pair-counting AUROC. O(n^2), fine for our scale.

    Returns None if either class is empty (AUROC undefined).
    """
    pos = [s for s, y in zip(scores, labels, strict=True) if y == 1]
    neg = [s for s, y in zip(scores, labels, strict=True) if y == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def _atomic_write_text(path: Path, text: str) -> None:
    """Write to a sibling .tmp then rename(atomic on POSIX) over target.

    A naive ``write_text`` truncates target on open, so a crash mid-write
    (disk full, signal, OOM) leaves a partial file. The site's
    ``JSON.parse`` would then silently fall back to EmptyState on the
    next deploy. Same-directory tmp file ensures the rename stays
    atomic across the same filesystem.
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def _clean_nans(obj: Any) -> Any:
    """Recursively replace NaN floats with None.

    Required because pandas/numpy emit NaN for missing values in
    to_dict(orient='records'), but the JSON spec doesn't define NaN.
    Strict parsers (e.g. JSON.parse in browsers) reject the document
    silently — masking the failure as 'no data' rather than an error.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _clean_nans(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_nans(v) for v in obj]
    return obj


# Inspect-AI's graded scorers (TruthfulQA's `choice`, SimpleQA's
# `schema_tool_graded_scorer`) emit categorical strings, not floats.
# Map them so per-row scores aggregate alongside our numeric scorers.
_CATEGORICAL_SCORE: dict[str, float] = {
    "c": 1.0, "correct": 1.0, "true": 1.0, "yes": 1.0,
    "i": 0.0, "incorrect": 0.0, "false": 0.0, "no": 0.0,
    "p": 0.5, "partial": 0.5,
    "n": 0.0, "not_attempted": 0.0,  # SimpleQA's "not attempted" grade
}


def _as_float(v: Any) -> float | None:
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cat = _CATEGORICAL_SCORE.get(v.strip().lower())
        if cat is not None:
            return cat
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("log_dir", type=Path)
    p.add_argument("--format", choices=["parquet", "csv", "json"], default="parquet")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output file path; stdout if omitted.")
    p.add_argument("--evals-dir", type=Path, default=REPO_ROOT / "evals",
                   help="Path to evals/ folder for source metadata.")
    args = p.parse_args()

    df = rollup(args.log_dir)
    if df.empty:
        print(f"No rows produced from {args.log_dir}.", file=sys.stderr)
        return 1

    evals_meta = collect_eval_meta(args.evals_dir)
    calib_stats = calibration_stats(df)
    external_baselines = collect_external_baselines(df)
    failures = collect_failures(df)
    _, judge_failures = _staleness_helpers()
    judge_failures(failures)
    fail_summary = failure_summary(failures)
    # Token usage + cost. Re-traverses the logs (separate ModelUsage path
    # from the per-sample row extraction above) — cheap relative to the
    # full rollup and cleanly isolated.
    usage_rows = _collect_usage(args.log_dir)
    bias_rows = collect_bias()

    if args.format == "csv":
        if args.output:
            df.to_csv(args.output, index=False)
        else:
            df.to_csv(sys.stdout, index=False)
    elif args.format == "json":
        # pandas emits NaN for missing values; that's not valid JSON and
        # JSON.parse() in the site silently falls back to EMPTY rollup.
        # Convert to None at serialization time so the wire format
        # round-trips through any strict parser.
        records = [_clean_nans(rec) for rec in df.to_dict(orient="records")]
        payload = {
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "n_rows": len(df),
            "evals": sorted(df["eval"].dropna().unique().tolist()),
            "providers": sorted(df["provider"].dropna().unique().tolist()),
            "scorers": sorted(df["scorer"].dropna().unique().tolist()),
            "evals_meta": evals_meta,
            "calibration_stats": calib_stats,
            "external_baselines": external_baselines,
            "failures": failures,
            "failure_thresholds": _FAILURE_THRESHOLDS,
            "failure_summary": fail_summary,
            "usage": usage_rows,
            "bias": bias_rows,
            "rows": records,
        }
        text = _json.dumps(payload, default=str, indent=2, allow_nan=False)
        if args.output:
            _atomic_write_text(args.output, text)
        else:
            sys.stdout.write(text)
    else:
        if args.output:
            df.to_parquet(args.output, index=False)
        else:
            df.to_parquet(sys.stdout.buffer, index=False)

    print(f"{len(df)} rows from {df['eval'].nunique()} evals, "
          f"{df['provider'].nunique()} providers, {df['scorer'].nunique()} scorers.",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
