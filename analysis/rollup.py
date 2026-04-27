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
            persona_name = _persona_label(persona)
            scores = sample.scores or {}
            for scorer_name, score in scores.items():
                rows.append(
                    {
                        "eval": eval_name,
                        "task_id": sample.id,
                        "provider": provider,
                        "persona": persona_name,
                        "domain": meta.get("domain"),
                        "subdomain": meta.get("subdomain"),
                        "difficulty": meta.get("difficulty"),
                        "tags": ",".join(meta.get("tags") or []),
                        "scorer": scorer_name,
                        "score": _as_float(score.value),
                        "explanation": score.explanation or "",
                        "sub_scores": (score.metadata or {}).get("sub_scores"),
                    }
                )
    return pd.DataFrame(rows)


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

    if args.format == "csv":
        if args.output:
            df.to_csv(args.output, index=False)
        else:
            df.to_csv(sys.stdout, index=False)
    elif args.format == "json":
        payload = {
            "generated_at": pd.Timestamp.now(tz="UTC").isoformat(),
            "n_rows": len(df),
            "evals": sorted(df["eval"].dropna().unique().tolist()),
            "providers": sorted(df["provider"].dropna().unique().tolist()),
            "scorers": sorted(df["scorer"].dropna().unique().tolist()),
            "evals_meta": evals_meta,
            "rows": df.to_dict(orient="records"),
        }
        text = _json.dumps(payload, default=str, indent=2)
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
