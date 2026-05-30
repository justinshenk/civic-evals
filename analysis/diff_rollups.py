"""Diff two ``rollup.json`` files and print a markdown summary.

A regenerated rollup is a wall of JSON; without a structural diff the PR
that commits it is unreviewable. This script reduces a before/after pair
to the cells whose mean score actually moved by more than ``--threshold``
(default 0.02 = 2 percentage points), plus the cells that newly appeared
or disappeared. Output is markdown so it pastes cleanly into a PR body
or a Slack post.

What this *doesn't* do: it doesn't claim statistical significance. With
N=5–15 per cell after persona expansion, a 0.05 swing is well inside the
noise floor — a CI band on each mean (issue #1 from the improvements
list) is the right surface for that, not this report. Read this script's
output as "here's what changed numerically" and use it to decide where
to *look*, not where to draw conclusions.

Usage::

    python analysis/diff_rollups.py old.json new.json
    python analysis/diff_rollups.py old.json new.json --threshold 0.05
    python analysis/diff_rollups.py old.json new.json --no-cost  # skip $ section
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# ---- helpers ---------------------------------------------------------------


def _mean(xs: Iterable[float]) -> float | None:
    vals = [x for x in xs if isinstance(x, (int, float))]
    return sum(vals) / len(vals) if vals else None


def _arrow(delta: float) -> str:
    if delta > 0:
        return "▲"
    if delta < 0:
        return "▼"
    return "·"


def _fmt(v: float | None, digits: int = 3) -> str:
    return "—" if v is None else f"{v:.{digits}f}"


def _fmt_delta(delta: float | None, digits: int = 3) -> str:
    if delta is None:
        return "—"
    return f"{delta:+.{digits}f}"


def _fmt_money(v: float | None) -> str:
    return "—" if v is None else f"${v:,.4f}"


def _fmt_money_delta(delta: float | None) -> str:
    if delta is None:
        return "—"
    sign = "+" if delta >= 0 else "−"
    return f"{sign}${abs(delta):,.4f}"


# ---- aggregations ----------------------------------------------------------


def _cell_means(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], float]:
    """Mean ``score`` per (eval, scorer, provider) tuple.

    Only includes cells with at least one non-null score — empty cells
    are dropped so they show up as ``appeared``/``disappeared`` against
    the other rollup rather than as a delta-from-None.
    """
    buckets: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    for r in rows:
        score = r.get("score")
        if not isinstance(score, (int, float)):
            continue
        key = (r.get("eval", "?"), r.get("scorer", "?"), r.get("provider", "?"))
        buckets[key].append(float(score))
    return {k: sum(v) / len(v) for k, v in buckets.items() if v}


def _cell_counts(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], int]:
    """Row count per (eval, scorer, provider) tuple, regardless of score."""
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in rows:
        key = (r.get("eval", "?"), r.get("scorer", "?"), r.get("provider", "?"))
        counts[key] += 1
    return dict(counts)


def _usage_costs(usage: list[dict[str, Any]]) -> dict[tuple[str, str], float]:
    """Total cost_usd per (eval, model). ``None`` costs treated as 0."""
    out: dict[tuple[str, str], float] = {}
    for u in usage or []:
        key = (u.get("eval", "?"), u.get("model", "?"))
        cost = u.get("cost_usd") or 0.0
        out[key] = out.get(key, 0.0) + float(cost)
    return out


def _failure_counts(failures: list[dict[str, Any]]) -> dict[str, int]:
    """Failures per eval — a quick 'did we get more confidently-wrong?'."""
    counts: dict[str, int] = defaultdict(int)
    for f in failures or []:
        counts[f.get("eval", "?")] += 1
    return dict(counts)


# ---- rendering -------------------------------------------------------------


def _render_score_section(
    old: dict[tuple[str, str, str], float],
    new: dict[tuple[str, str, str], float],
    counts_old: dict[tuple[str, str, str], int],
    counts_new: dict[tuple[str, str, str], int],
    threshold: float,
) -> list[str]:
    keys = sorted(set(old) | set(new))
    moved: list[tuple[tuple[str, str, str], float, float, float]] = []
    appeared: list[tuple[tuple[str, str, str], float]] = []
    disappeared: list[tuple[tuple[str, str, str], float]] = []
    for k in keys:
        if k in old and k in new:
            d = new[k] - old[k]
            if abs(d) >= threshold:
                moved.append((k, old[k], new[k], d))
        elif k in new:
            appeared.append((k, new[k]))
        else:
            disappeared.append((k, old[k]))

    out: list[str] = []
    out.append("## Mean score by (eval, scorer, provider)")
    out.append("")
    if not moved and not appeared and not disappeared:
        out.append(f"_No cells moved by more than {threshold:.2f}._")
        out.append("")
        return out

    if moved:
        # Sort by |delta| desc so the eye lands on the biggest swings first.
        moved.sort(key=lambda x: -abs(x[3]))
        out.append("| eval | scorer | provider | old | new | Δ | n |")
        out.append("|---|---|---|---:|---:|---:|---:|")
        for (e, s, p), o, n, d in moved:
            n_old = counts_old.get((e, s, p), 0)
            n_new = counts_new.get((e, s, p), 0)
            n_cell = f"{n_new}" if n_old == n_new else f"{n_old}→{n_new}"
            out.append(
                f"| {e} | {s} | `{p}` | {_fmt(o)} | {_fmt(n)} | "
                f"{_arrow(d)} {_fmt_delta(d)} | {n_cell} |"
            )
        out.append("")

    if appeared:
        appeared.sort(key=lambda x: (x[0][0], x[0][1], x[0][2]))
        out.append("**Appeared** (new cells in the new rollup):")
        out.append("")
        for (e, s, p), v in appeared:
            n = counts_new.get((e, s, p), 0)
            out.append(f"- {e} / {s} / `{p}` → {_fmt(v)} (n={n})")
        out.append("")

    if disappeared:
        disappeared.sort(key=lambda x: (x[0][0], x[0][1], x[0][2]))
        out.append("**Disappeared** (cells present in old, gone in new):")
        out.append("")
        for (e, s, p), v in disappeared:
            n = counts_old.get((e, s, p), 0)
            out.append(f"- {e} / {s} / `{p}` was {_fmt(v)} (n={n})")
        out.append("")
    return out


def _render_failure_section(
    old: dict[str, int],
    new: dict[str, int],
) -> list[str]:
    keys = sorted(set(old) | set(new))
    rows = []
    for k in keys:
        o = old.get(k, 0)
        n = new.get(k, 0)
        if o == n:
            continue
        rows.append((k, o, n, n - o))
    out: list[str] = []
    out.append("## Flagged failures by eval")
    out.append("")
    if not rows:
        out.append("_No change in failure counts._")
        out.append("")
        return out
    rows.sort(key=lambda r: -abs(r[3]))
    out.append("| eval | old | new | Δ |")
    out.append("|---|---:|---:|---:|")
    for k, o, n, d in rows:
        out.append(f"| {k} | {o} | {n} | {_arrow(d)} {d:+d} |")
    out.append("")
    return out


def _render_cost_section(
    old: dict[tuple[str, str], float],
    new: dict[tuple[str, str], float],
    threshold_usd: float = 0.001,
) -> list[str]:
    keys = sorted(set(old) | set(new))
    rows = []
    for k in keys:
        o = old.get(k)
        n = new.get(k)
        if o is None and n is None:
            continue
        d = (n or 0.0) - (o or 0.0)
        if abs(d) < threshold_usd:
            continue
        rows.append((k, o, n, d))
    out: list[str] = []
    out.append("## API cost by (eval, model)")
    out.append("")
    if not rows:
        out.append("_No cost cells moved by more than $0.001 (or no usage block in either rollup)._")
        out.append("")
        return out
    rows.sort(key=lambda r: -abs(r[3]))
    out.append("| eval | model | old | new | Δ |")
    out.append("|---|---|---:|---:|---:|")
    for (e, m), o, n, d in rows:
        out.append(
            f"| {e} | `{m}` | {_fmt_money(o)} | {_fmt_money(n)} | {_fmt_money_delta(d)} |"
        )
    out.append("")
    return out


def _render_header(
    old: dict[str, Any],
    new: dict[str, Any],
    old_path: Path,
    new_path: Path,
    threshold: float,
) -> list[str]:
    out: list[str] = []
    out.append(f"# rollup diff: `{old_path.name}` → `{new_path.name}`")
    out.append("")
    out.append(
        f"_Threshold: |Δmean| ≥ {threshold:.2f}. Cells inside the threshold are "
        "elided._"
    )
    out.append("")
    out.append("| | old | new |")
    out.append("|---|---|---|")
    out.append(
        f"| generated_at | {old.get('generated_at', '—')} | {new.get('generated_at', '—')} |"
    )
    out.append(f"| n_rows | {old.get('n_rows', '—')} | {new.get('n_rows', '—')} |")
    out.append(
        f"| evals | {len(old.get('evals') or [])} | {len(new.get('evals') or [])} |"
    )
    out.append(
        f"| providers | {len(old.get('providers') or [])} | {len(new.get('providers') or [])} |"
    )
    out.append("")
    return out


def render(
    old: dict[str, Any],
    new: dict[str, Any],
    *,
    old_path: Path,
    new_path: Path,
    threshold: float,
    include_cost: bool = True,
) -> str:
    parts: list[str] = []
    parts += _render_header(old, new, old_path, new_path, threshold)
    parts += _render_score_section(
        _cell_means(old.get("rows", [])),
        _cell_means(new.get("rows", [])),
        _cell_counts(old.get("rows", [])),
        _cell_counts(new.get("rows", [])),
        threshold=threshold,
    )
    parts += _render_failure_section(
        _failure_counts(old.get("failures", [])),
        _failure_counts(new.get("failures", [])),
    )
    if include_cost:
        parts += _render_cost_section(
            _usage_costs(old.get("usage", []) or []),
            _usage_costs(new.get("usage", []) or []),
        )
    return "\n".join(parts).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("old", type=Path, help="Path to the older rollup.json")
    p.add_argument("new", type=Path, help="Path to the newer rollup.json")
    p.add_argument(
        "--threshold",
        type=float,
        default=0.02,
        help="Min |Δmean| to surface a moved cell (default 0.02 = 2pp).",
    )
    p.add_argument(
        "--no-cost",
        action="store_true",
        help="Skip the API-cost section (useful when usage data is missing).",
    )
    args = p.parse_args(argv)
    for path in (args.old, args.new):
        if not path.exists():
            print(f"Not found: {path}", file=sys.stderr)
            return 1
    old = json.loads(args.old.read_text())
    new = json.loads(args.new.read_text())
    print(
        render(
            old,
            new,
            old_path=args.old,
            new_path=args.new,
            threshold=args.threshold,
            include_cost=not args.no_cost,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
