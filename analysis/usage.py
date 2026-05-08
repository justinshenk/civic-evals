"""Token usage + API cost reporter.

Walks an inspect-ai logs directory, sums ``model_usage`` across runs,
joins against ``analysis.pricing`` to produce a USD cost, and prints a
markdown table grouped by (eval, model).

Usage:
    uv run python analysis/usage.py logs/
    uv run python analysis/usage.py logs/ --json    # machine-readable
    uv run python analysis/usage.py logs/ --since 2026-04-01

Designed to be importable too: ``collect_usage()`` returns a list of
dicts that ``rollup.py`` embeds into ``rollup.json`` so the site and
the Slack digest read it without re-traversing the logs.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from inspect_ai.log import list_eval_logs, read_eval_log

# Allow running as a script (``python analysis/usage.py``) where
# ``analysis`` isn't a package on sys.path. Mirrors the staleness-judge
# import dance in rollup.py.
try:
    from analysis.pricing import cost_for_usage
except ModuleNotFoundError:
    from pricing import cost_for_usage  # type: ignore[no-redef]


@dataclass
class UsageRow:
    """One row per (eval, model). Tokens summed across all runs for
    that pair; cost summed alongside. ``cost_source`` is the worst-case
    source across the underlying runs — if any run was estimated, the
    aggregate is marked estimated."""

    eval: str
    model: str
    n_runs: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = 0.0
    cost_source: str = "reported"  # "reported" | "computed" | "mixed" | "unknown"
    unknown_models: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        # Drop the internal-only diag list from the persisted shape.
        d.pop("unknown_models", None)
        return d


def _eval_log_files(log_dir: Path, since: datetime | None) -> list[str]:
    """List eval logs, optionally filtered by file mtime."""
    files = list_eval_logs(str(log_dir))
    if since is None:
        return files
    cutoff = since.timestamp()
    out = []
    for f in files:
        # ``list_eval_logs`` returns string paths; guard against URI forms.
        try:
            mtime = Path(f).stat().st_mtime
        except (OSError, ValueError):
            continue
        if mtime >= cutoff:
            out.append(f)
    return out


def collect_usage(log_dir: Path, *, since: datetime | None = None) -> list[dict[str, Any]]:
    """Aggregate token usage and cost per (eval, model). One row per pair.

    Returns a list of plain dicts (suitable for JSON serialization).
    Cost source is "reported" only if every contributing run reported a
    cost; "computed" only if every contributing run was priced from the
    table; "mixed" if both; "unknown" if any contributing model lacked
    both a reported cost and a price table entry.
    """
    bucket: dict[tuple[str, str], UsageRow] = defaultdict(
        lambda: UsageRow(eval="", model="")
    )
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)

    for log_file in _eval_log_files(log_dir, since):
        log = read_eval_log(log_file)
        eval_name = log.eval.task or ""
        stats = getattr(log, "stats", None)
        usage_map = getattr(stats, "model_usage", None) or {}
        for model, usage in usage_map.items():
            key = (eval_name, model)
            row = bucket[key]
            row.eval = eval_name
            row.model = model
            row.n_runs += 1
            row.input_tokens += usage.input_tokens or 0
            row.output_tokens += usage.output_tokens or 0
            row.cache_read_tokens += usage.input_tokens_cache_read or 0
            row.cache_write_tokens += usage.input_tokens_cache_write or 0
            row.reasoning_tokens += usage.reasoning_tokens or 0
            row.total_tokens += usage.total_tokens or 0
            cost, src = cost_for_usage(
                model,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                input_tokens_cache_read=usage.input_tokens_cache_read,
                input_tokens_cache_write=usage.input_tokens_cache_write,
                reasoning_tokens=usage.reasoning_tokens,
                reported_cost=getattr(usage, "total_cost", None),
            )
            sources[key].add(src)
            if src == "unknown":
                if model not in row.unknown_models:
                    row.unknown_models.append(model)
                # Don't poison the running total with None; just stop summing.
                if row.cost_usd is not None:
                    row.cost_usd = None
            elif row.cost_usd is not None and cost is not None:
                row.cost_usd += cost

    # Resolve aggregate cost_source per row.
    rows: list[dict[str, Any]] = []
    for key, row in bucket.items():
        srcs = sources[key]
        if "unknown" in srcs:
            row.cost_source = "unknown"
        elif srcs == {"reported"}:
            row.cost_source = "reported"
        elif srcs == {"computed"}:
            row.cost_source = "computed"
        else:
            row.cost_source = "mixed"
        rows.append(row.to_dict())

    rows.sort(key=lambda r: (r["eval"], r["model"]))
    return rows


# --------------------------------------------------------------------------
# CLI rendering
# --------------------------------------------------------------------------


def _fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _fmt_cost(c: float | None, source: str) -> str:
    if c is None:
        return "—"
    suffix = {"reported": "", "computed": "*", "mixed": "*", "unknown": "?"}.get(source, "")
    return f"${c:,.2f}{suffix}"


def render_markdown(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No eval logs found._"
    out: list[str] = []
    out.append("| eval | model | runs | input | output | reasoning | total | cost |")
    out.append("|---|---|--:|--:|--:|--:|--:|--:|")
    total_in = total_out = total_total = 0
    total_cost: float | None = 0.0
    any_estimated = False
    for r in rows:
        out.append(
            "| {eval} | `{model}` | {runs} | {inp} | {outp} | {reas} | {tot} | {cost} |".format(
                eval=r["eval"],
                model=r["model"],
                runs=r["n_runs"],
                inp=_fmt_tokens(r["input_tokens"]),
                outp=_fmt_tokens(r["output_tokens"]),
                reas=_fmt_tokens(r["reasoning_tokens"]),
                tot=_fmt_tokens(r["total_tokens"]),
                cost=_fmt_cost(r["cost_usd"], r["cost_source"]),
            )
        )
        total_in += r["input_tokens"]
        total_out += r["output_tokens"]
        total_total += r["total_tokens"]
        if r["cost_usd"] is None:
            total_cost = None
        elif total_cost is not None:
            total_cost += r["cost_usd"]
        if r["cost_source"] in ("computed", "mixed"):
            any_estimated = True

    out.append(
        "| **total** | — | — | **{inp}** | **{outp}** | — | **{tot}** | **{cost}** |".format(
            inp=_fmt_tokens(total_in),
            outp=_fmt_tokens(total_out),
            tot=_fmt_tokens(total_total),
            cost=_fmt_cost(total_cost, "computed" if any_estimated else "reported"),
        )
    )
    if any_estimated:
        out.append("")
        out.append("`*` cost estimated from `analysis/pricing.py` (provider didn't report).")
    unknown = sorted({m for r in rows for m in r.get("unknown_models", [])})
    if unknown:
        out.append("")
        out.append(f"`?` price unknown for: {', '.join(f'`{m}`' for m in unknown)}.")
        out.append("Add a row to `analysis/pricing.py` to include in totals.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("log_dir", type=Path, help="inspect-ai logs directory")
    p.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON instead of markdown"
    )
    p.add_argument(
        "--since",
        type=lambda s: datetime.fromisoformat(s),
        default=None,
        help="only include logs modified since this ISO date (e.g. 2026-04-01)",
    )
    args = p.parse_args(argv)

    rows = collect_usage(args.log_dir, since=args.since)
    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(render_markdown(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
