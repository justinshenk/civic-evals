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
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from inspect_ai.log import list_eval_logs, read_eval_log


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
    args = p.parse_args()

    df = rollup(args.log_dir)
    if df.empty:
        print(f"No rows produced from {args.log_dir}.", file=sys.stderr)
        return 1

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
            "rows": df.to_dict(orient="records"),
        }
        import json as _json
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
