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
_DIAG_KEYS = ("truth", "estimate", "ci_low", "ci_high", "parse_success")


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

        out.append(
            {
                "name": d.name,
                "description": _readme_summary(d / "README.md"),
                "task_count": len(tasks),
                "difficulty": dict(sorted(difficulties.items())),
                "subdomains": subdomains,
                "personas_used": personas,
                "scorer_kinds": scorer_kinds,
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
                    "AUROC of (1/CI-width) vs (point estimate within ±10% of truth). "
                    "Higher = narrower CIs on questions the model gets right."
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
            t = float(truth)
            if t == 0:
                point = 1.0 if float(est) == 0 else 0.0
            else:
                rel = abs(float(est) - t) / abs(t)
                point = 1.0 if rel <= 0.10 else max(0.0, 1.0 - (rel - 0.10) / 0.90)

    return width_rel, point


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


def _as_float(v: Any) -> float | None:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, bool):
        return float(v)
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
            "rows": records,
        }
        text = _json.dumps(payload, default=str, indent=2, allow_nan=False)
        if args.output:
            args.output.write_text(text)
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
