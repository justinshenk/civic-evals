"""Generate a Slack-block summary of a rollup.json.

Reads ``site/public/data/rollup.json`` (or whatever path is passed) and
emits a Slack incoming-webhook payload to stdout. The webhook URL itself
is not handled here — the workflow does the actual POST so the secret
never leaves the runner step.

Two modes:
- ``--mode success`` (default): per-eval × provider mean table, external
  baselines, calibration AUROC, optional delta vs a prior rollup.
- ``--mode failure``: a short message pointing at the failed workflow run.

Usage:
    python analysis/slack_summary.py site/public/data/rollup.json \\
        --prior /tmp/prior_rollup.json \\
        --run-url https://github.com/owner/repo/actions/runs/123 \\
        > /tmp/payload.json
    curl -X POST -H 'Content-Type: application/json' \\
        --data @/tmp/payload.json "$SLACK_WEBHOOK_URL"
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SITE_URL = "https://civicevals.vercel.app/"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("rollup", type=Path, nargs="?")
    p.add_argument("--prior", type=Path, default=None,
                   help="Optional previous rollup.json for delta computation.")
    p.add_argument("--mode", choices=["success", "failure"], default="success")
    p.add_argument("--run-url", default=None,
                   help="GitHub Actions run URL to link in the message.")
    p.add_argument("--commit-sha", default=None,
                   help="Short commit SHA for the post-commit message.")
    args = p.parse_args()

    if args.mode == "failure":
        sys.stdout.write(json.dumps(_failure_payload(args.run_url), indent=2))
        return 0

    if not args.rollup or not args.rollup.exists():
        sys.stderr.write(f"rollup not found at {args.rollup}\n")
        return 1

    current = json.loads(args.rollup.read_text())
    prior = json.loads(args.prior.read_text()) if args.prior and args.prior.exists() else None

    payload = _success_payload(current, prior, args.run_url, args.commit_sha)
    sys.stdout.write(json.dumps(payload, indent=2))
    return 0


def _failure_payload(run_url: str | None) -> dict[str, Any]:
    text = "civic-evals refresh failed"
    if run_url:
        text += f" — <{run_url}|view run>"
    return {
        "text": text,
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        ":warning: *civic-evals refresh failed*\n"
                        + (f"<{run_url}|View run logs>" if run_url else "")
                    ),
                },
            },
        ],
    }


def _success_payload(
    current: dict[str, Any],
    prior: dict[str, Any] | None,
    run_url: str | None,
    commit_sha: str | None,
) -> dict[str, Any]:
    means = _eval_provider_means(current)
    prior_means = _eval_provider_means(prior) if prior else {}

    summary_lines = _format_eval_table(means, prior_means)
    baseline_lines = _format_baselines(current)
    calib_lines = _format_calibration(current)

    header_text = ":bar_chart: *civic-evals refresh complete*"
    meta_bits = []
    if commit_sha:
        meta_bits.append(f"`{commit_sha}`")
    meta_bits.append(f"{current.get('n_rows', 0)} rows")
    meta_bits.append(f"{len(current.get('providers') or [])} providers")
    if run_url:
        meta_bits.append(f"<{run_url}|run>")
    meta_bits.append(f"<{SITE_URL}|site>")
    meta_text = " · ".join(meta_bits)

    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": header_text + "\n" + meta_text},
        },
    ]
    if summary_lines:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Mean score by eval × provider*\n```\n"
                        + "\n".join(summary_lines) + "\n```",
            },
        })
    if calib_lines:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": "*Calibration AUROC*\n" + "\n".join(calib_lines)},
        })
    if baseline_lines:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn",
                     "text": "*External baselines*\n" + "\n".join(baseline_lines)},
        })

    # Slack truncates `text` for notifications/previews; keep it short.
    fallback = f"civic-evals refresh: {current.get('n_rows', 0)} rows across {len(current.get('evals') or [])} evals."
    return {"text": fallback, "blocks": blocks}


def _eval_provider_means(
    rollup: dict[str, Any] | None,
) -> dict[tuple[str, str], float]:
    """Mean score per (eval, provider). Skips rows with score=None."""
    if not rollup:
        return {}
    bucket: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rollup.get("rows") or []:
        score = row.get("score")
        if not isinstance(score, (int, float)):
            continue
        eval_name = row.get("eval")
        provider = row.get("provider")
        if not eval_name or not provider:
            continue
        bucket[(eval_name, provider)].append(float(score))
    return {k: sum(vs) / len(vs) for k, vs in bucket.items() if vs}


def _format_eval_table(
    means: dict[tuple[str, str], float],
    prior_means: dict[tuple[str, str], float],
) -> list[str]:
    """Fixed-width table for monospace block. Includes Δ vs prior when available."""
    if not means:
        return []
    evals = sorted({e for e, _ in means})
    providers = sorted({p for _, p in means})

    # Short provider column header to fit Slack's narrow column.
    header = ["eval".ljust(34)] + [_short_provider(p).rjust(18) for p in providers]
    rows = ["  ".join(header)]
    rows.append("-" * len(rows[0]))
    for ev in evals:
        cells = [ev.ljust(34)]
        for p in providers:
            cur = means.get((ev, p))
            prv = prior_means.get((ev, p))
            cells.append(_format_score_cell(cur, prv).rjust(18))
        rows.append("  ".join(cells))
    return rows


def _format_score_cell(cur: float | None, prv: float | None) -> str:
    if cur is None:
        return "—"
    if prv is None:
        return f"{cur:.3f}"
    delta = cur - prv
    arrow = "▲" if delta > 0.005 else "▼" if delta < -0.005 else "·"
    return f"{cur:.3f} {arrow}{abs(delta):.3f}"


def _short_provider(p: str) -> str:
    """Compact provider tag for narrow columns."""
    if "/" in p:
        family, name = p.split("/", 1)
        return f"{family[:3]}:{name[-12:]}"
    return p[:18]


def _format_calibration(rollup: dict[str, Any]) -> list[str]:
    stats = rollup.get("calibration_stats") or []
    out = []
    for s in stats:
        v = s.get("value")
        if v is None:
            tag = f"_n={s.get('n', 0)}, AUROC undefined_"
        else:
            tag = f"AUROC *{v:.3f}* (n={s.get('n', 0)}, {s.get('n_correct', 0)} correct)"
        out.append(f"• `{s.get('eval')}` · `{s.get('provider')}` — {tag}")
    return out


def _format_baselines(rollup: dict[str, Any]) -> list[str]:
    baselines = rollup.get("external_baselines") or []
    means = _eval_provider_means(rollup)
    out = []
    for b in baselines:
        per_provider = []
        for prov in b.get("providers") or []:
            score = means.get((b.get("name"), prov))
            score_str = f"{score:.3f}" if isinstance(score, (int, float)) else "—"
            per_provider.append(f"{_short_provider(prov)}: {score_str}")
        per_provider_str = ", ".join(per_provider) if per_provider else "no runs"
        out.append(f"• *{b.get('title')}* (n={b.get('n_rows', 0)}) — {per_provider_str}")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
