"""Haiku replication of the persona_l0_mitigation experiment.

The Sonnet run showed ~67% gap reduction under an L0 fairness
instruction. This script repeats the exact same 3-cell x 4-persona x
2-condition x 10-rep design on Haiku to test whether the mitigation
generalizes or is Sonnet-specific.

Reuses persona_l0_mitigation.build_cell_config but overrides the model.

Cost: ~$1 with Haiku pricing.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import persona_l0_mitigation as l0
from civic_bias_experiment import estimate_cost, run

MODEL = "claude-haiku-4-5"


async def main_async() -> None:
    # Reuse the same target cells; override model.
    configs = [l0.build_cell_config(c, p, d) for (c, p, d) in l0.TARGET_CELLS]
    for cfg in configs:
        cfg.models = [MODEL]
        cfg.name = cfg.name.replace("l0_mitigation_", "l0_mitigation_haiku_")

    grand = sum(estimate_cost(cfg).total_dollars for cfg in configs)
    total_calls = sum(cfg.total_calls() for cfg in configs)
    print(f"Total calls: {total_calls}")
    print(f"Estimated cost ({MODEL}): ${grand:.2f}\n")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; aborting.")
        return

    all_rows: list[dict] = []
    for cfg in configs:
        print(f"=== {cfg.name} ===")
        rows = await run(cfg)
        all_rows.extend(rows)
        for cond in ("baseline", "L0"):
            means = {}
            for persona in ("left", "moderate", "unspecified", "right"):
                xs = [
                    r["rating"]
                    for r in rows
                    if r["instruction"] == cond
                    and r["user_persona"] == persona
                    and r["rating"] is not None
                ]
                if xs:
                    means[persona] = sum(xs) / len(xs)
            if "left" in means and "right" in means:
                gap = means["right"] - means["left"]
                line = "  ".join(
                    f"{p}={means.get(p, float('nan')):.2f}"
                    for p in ("left", "moderate", "unspecified", "right")
                )
                print(f"  {cond:<9} {line}  gap(R-L)={gap:+.2f}")

    out_path = Path(__file__).resolve().parent / "persona_l0_haiku_rows.json"
    out_path.write_text(json.dumps(all_rows, indent=2, default=str))
    print(f"\nSaved {len(all_rows)} rows -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main_async())
