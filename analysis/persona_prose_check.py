"""Targeted re-run of the highest-gap cells from the persona-bias pilot,
this time saving the response text. The pilot proved the rating swings
exist; this run lets us see HOW the model justifies the swing -- is the
reasoning different, or does the model produce essentially the same
prose with a different number?

Restricted to:
  - Sonnet only (rating swing was largest there)
  - 1 D candidate (cand-D1-progressive, the most-flipped D profile)
  - 1 R candidate (cand-R1-traditional, the most-flipped R profile)
  - 2 user personas (left, right) -- the two endpoints
  - 1 Claude priming (unprompted) -- isolate the user-persona axis
  - 1 depth (thorough) -- gives the model room to reason
  - 5 replicates per cell -> 2 cands x 2 personas x 5 reps = 20 calls
  - ~$0.25

The full pilot had rating swings of -1.83 (cand-D1, Sonnet) and +1.89
(cand-R1, Sonnet) between left- and right-user persona. If those
swings come from genuine reasoning differences, the prose should
show different arguments; if they come from sycophancy alone, the
prose will be similar and only the number will differ.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import the persona expansion + candidate definitions from the pilot
# so we use the EXACT same prompts as the headline pilot. Importing the
# module also re-applies the render() monkey-patch.
import persona_bias_pilot as pilot  # noqa: F401, E402
from civic_bias_experiment import (
    ExperimentConfig,
    Factor,
    estimate_cost,
    format_cost_estimate,
    persist,
    run,
)

# Filter the pilot's candidate set down to the two most-flipped ones.
TARGET_CIDS = ("cand-D1-progressive", "cand-R1-traditional")
QUESTIONS = [q for q in pilot.QUESTIONS if q.id in TARGET_CIDS]

# Strip the factors down to a single axis we want to inspect: user_persona.
FACTORS = [
    Factor(
        name="user_persona",
        levels=("left", "right"),
        ordinal={"left": 0.0, "right": 1.0},
        kind="protected",
    ),
    Factor(
        name="claude_priming",
        levels=("unprompted",),
        kind="protected",
    ),
    Factor(
        name="depth",
        levels=("thorough",),
        ordinal={"thorough": 1.0},
        kind="legitimate",
    ),
]


CONFIG = ExperimentConfig(
    name="persona_prose_check",
    questions=QUESTIONS,
    factors=FACTORS,
    system_prompt_template=pilot.SYSTEM_TEMPLATE,
    user_prompt_template=pilot.USER_TEMPLATE,
    models=["claude-sonnet-4-6"],
    n_reps=5,
    max_concurrency=4,
    max_tokens=2048,
    save_responses=True,
)


async def main_async() -> None:
    print(format_cost_estimate(estimate_cost(CONFIG)))
    print()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; aborting.")
        return

    rows = await run(CONFIG)
    n_parsed = sum(1 for r in rows if r["rating"] is not None)
    print(f"\nGot {len(rows)} rows; {n_parsed} parsed.")

    # Per-cell summary
    print("\n=== Per-cell mean ratings ===")
    from collections import defaultdict
    cells: dict[tuple, list[float]] = defaultdict(list)
    for r in rows:
        if r["rating"] is None:
            continue
        key = (r["question_id"], r["user_persona"])
        cells[key].append(r["rating"])
    for k, vs in sorted(cells.items()):
        import statistics as st
        print(f"  {k[0]:<26} user={k[1]:<6}  n={len(vs)}  mean={st.mean(vs):.2f}  range=[{min(vs)},{max(vs)}]")

    # Persist with response text
    out_dir = Path(__file__).resolve().parent
    rows_path, fits_path = persist(rows, {"per_question": {}, "pooled": {}}, out_dir, CONFIG.name)
    print(f"\nSaved:\n  {rows_path}")


if __name__ == "__main__":
    asyncio.run(main_async())
