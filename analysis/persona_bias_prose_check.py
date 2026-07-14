"""Targeted prose-check on the largest persona-gap cells from the pilot.

The pilot showed Sonnet swinging the rating by 3+ points on the SAME
candidate between left-leaning and right-leaning user personas in some
configurations. That number doesn't tell us whether the model's
reasoning changed, or whether the prose stayed the same and only the
numeric rating moved.

This script:
  1. Picks the 3 (candidate, priming, depth) cells with the largest
     pilot |right - left| rating gap on Sonnet.
  2. Runs each cell across all 4 personas, 10 reps each = 120 calls.
  3. Saves the full response text so we can read what the model said
     under each persona condition.

Cost: ~$1.50 with Sonnet ($0.012/call x 120 calls).

Output: analysis/persona_bias_prose_check_rows.json with response_text
populated, plus a short summary printed.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reuse the candidate profiles, persona expansions, priming text, and
# the render patch from the pilot.
import persona_bias_pilot as pilot  # noqa: F401  (also installs render patch)
from civic_bias_experiment import (
    ExperimentConfig,
    Factor,
    estimate_cost,
    run,
)
from persona_bias_pilot import CANDIDATE_PROFILES, _candidate_question

# Pick the 3 highest-gap cells from the pilot (see prior summary):
#   (candidate, claude_priming, depth)
TARGET_CELLS = [
    ("cand-D1-progressive", "republican-primed", "thorough"),  # Δ = -3.67
    ("cand-R2-fiscal",       "democrat-primed",   "thorough"),  # Δ = +3.00
    ("cand-R1-traditional",  "democrat-primed",   "brief"),     # Δ = +3.00
]

# We re-run each target candidate across all 4 personas at the target
# priming + depth. The infra runs the FULL factorial, so we either (a)
# rebuild a stripped-down factorial per cell, or (b) accept that we'll
# rerun adjacent cells too. (a) is cheaper and gives cleaner data.

# Build one ExperimentConfig per cell: 4 personas, 1 priming, 1 depth,
# 1 candidate, 10 reps, 1 model. = 40 calls per cell, 120 total.

MODEL = "claude-sonnet-4-6"
N_REPS = 10
N_CONCURRENCY = 8

# Pre-fetch the candidate Question objects keyed by id.
ALL_QUESTIONS = {q.id: q for q in (_candidate_question(*c) for c in CANDIDATE_PROFILES)}


def build_cell_config(cand_id: str, priming: str, depth: str) -> ExperimentConfig:
    question = ALL_QUESTIONS[cand_id]
    name = f"prose_check_{cand_id}_{priming}_{depth}"
    return ExperimentConfig(
        name=name,
        questions=[question],
        factors=[
            Factor(
                name="user_persona",
                levels=("left", "moderate", "unspecified", "right"),
                ordinal={"left": 0.0, "moderate": 1.0, "unspecified": 1.5, "right": 2.0},
                kind="protected",
            ),
            Factor(
                name="claude_priming",
                levels=(priming,),
                ordinal={priming: 0.0},
                kind="protected",
            ),
            Factor(
                name="depth",
                levels=(depth,),
                ordinal={depth: 0.0},
                kind="legitimate",
            ),
        ],
        system_prompt_template=pilot.SYSTEM_TEMPLATE,
        user_prompt_template=pilot.USER_TEMPLATE,
        models=[MODEL],
        n_reps=N_REPS,
        max_concurrency=N_CONCURRENCY,
        max_tokens=1024,
        save_responses=True,
    )


async def main_async() -> None:
    configs = [build_cell_config(c, p, d) for (c, p, d) in TARGET_CELLS]

    # Predicted total cost across all 3 cells.
    total_calls = sum(cfg.total_calls() for cfg in configs)
    print(f"Total targeted calls: {total_calls}")
    grand = 0.0
    for cfg in configs:
        breakdown = estimate_cost(cfg)
        print(f"  {cfg.name}: {cfg.total_calls()} calls, ${breakdown.total_dollars:.2f}")
        grand += breakdown.total_dollars
    print(f"GRAND TOTAL ESTIMATED: ${grand:.2f}\n")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; aborting.")
        return

    all_rows: list[dict] = []
    for cfg in configs:
        print(f"=== Running {cfg.name} ({cfg.total_calls()} calls) ===")
        rows = await run(cfg)
        n_parsed = sum(1 for r in rows if r["rating"] is not None)
        ratings_by_persona = {}
        for r in rows:
            ratings_by_persona.setdefault(r["user_persona"], []).append(r["rating"])
        print(f"  parsed: {n_parsed}/{len(rows)}")
        for persona in ("left", "moderate", "unspecified", "right"):
            xs = [x for x in ratings_by_persona.get(persona, []) if x is not None]
            if not xs:
                continue
            mean = sum(xs) / len(xs)
            print(f"  {persona:<12} n={len(xs):>2}  mean={mean:.2f}")
        all_rows.extend(rows)

    # Save the pooled rows for prose extraction.
    out_dir = Path(__file__).resolve().parent
    out_path = out_dir / "persona_bias_prose_check_rows.json"
    import json
    out_path.write_text(json.dumps(all_rows, indent=2, default=str))
    print(f"\nSaved {len(all_rows)} rows -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main_async())
