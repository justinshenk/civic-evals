"""Does L0 fairness framing work when placed in the user message instead
of the system message?

Background:
  - persona_l0_mitigation.py (Sonnet) showed L0 in the SYSTEM prompt
    shrinks the user-persona effect by ~67% across 3 cells.
  - Production deployments often do not fully control the system
    prompt -- the user-side message may be the only place a
    developer can inject instructions. If L0 only works as a system
    prompt, that's a real constraint on the mitigation recommendation.

Design:
  - Same 3 cells as the L0 mitigation run.
  - 4 personas.
  - 1 NEW condition: L0_user -- the L0 prefix is prepended to the
    USER message, not the system message. The system prompt is the
    plain priming (same as the "baseline" condition).
  - 10 reps per cell.
  - Sonnet only (where the effect is largest).

Total: 3 cells x 4 personas x 1 condition x 10 reps = 120 calls.
Cost: ~$1.50 on Sonnet.

Comparison reads against the existing L0_system data from
persona_l0_mitigation_rows.json (no re-run of system-side L0). The
final writeup is a three-way table: baseline | L0_system | L0_user.

If L0_user matches L0_system: prefix wording matters, placement doesn't.
If L0_user matches baseline: the model attends to instructions in the
  system slot specifically (a known instruction-following property).
If L0_user is between: partial mitigation; placement matters but not
  the only thing.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import civic_bias_experiment as cbe
import persona_bias_pilot as pilot
import persona_l0_mitigation as l0_mit
from civic_bias_experiment import (
    ExperimentConfig,
    Factor,
    estimate_cost,
    run,
)
from persona_l0_mitigation import L0_PREFIX, TARGET_CELLS

MODEL = "claude-sonnet-4-6"
N_REPS = 10
N_CONCURRENCY = 8


# Layer another render patch: handle a new "L0_user" instruction level.
# When instruction == "L0_user", the L0 prefix is prepended to the
# USER prompt, and the system prompt stays as plain priming.
_existing_render = cbe.render


def _placement_render(config, question, assignment):
    sys_p, user_p = _existing_render(config, question, assignment)
    if assignment.get("instruction") == "L0_user":
        # The existing render patch may have already added L0 to system
        # if instruction == "L0_user" got mistaken; strip and re-add.
        # In our config below we use ONLY "L0_user" so we'll never see
        # the L0_system prefix on sys_p here -- but guard anyway.
        if sys_p.startswith(L0_PREFIX):
            sys_p = sys_p[len(L0_PREFIX) :].lstrip("\n")
        user_p = L0_PREFIX + "\n\n" + user_p
    return sys_p, user_p


cbe.render = _placement_render


def build_cell_config(cand_id: str, priming: str, depth: str) -> ExperimentConfig:
    question = l0_mit.ALL_QUESTIONS[cand_id]
    return ExperimentConfig(
        name=f"l0_placement_{cand_id}_{priming}_{depth}",
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
            Factor(
                name="instruction",
                levels=("L0_user",),
                ordinal={"L0_user": 0.0},
                kind="legitimate",
            ),
        ],
        system_prompt_template=pilot.SYSTEM_TEMPLATE,
        user_prompt_template=pilot.USER_TEMPLATE,
        models=[MODEL],
        n_reps=N_REPS,
        max_concurrency=N_CONCURRENCY,
        max_tokens=1024,
        save_responses=False,
    )


def _load_system_baseline_data() -> dict:
    """Pull the baseline and L0 (system) cell means from the prior run."""
    path = Path(__file__).resolve().parent / "persona_l0_mitigation_rows.json"
    rows = json.loads(path.read_text())
    out: dict = {}
    for r in rows:
        if r["rating"] is None:
            continue
        key = (
            r["question_id"],
            r["claude_priming"],
            r["depth"],
            r["instruction"],
            r["user_persona"],
        )
        out.setdefault(key, []).append(r["rating"])
    return out


async def main_async() -> None:
    configs = [build_cell_config(c, p, d) for (c, p, d) in TARGET_CELLS]

    grand = sum(estimate_cost(cfg).total_dollars for cfg in configs)
    total_calls = sum(cfg.total_calls() for cfg in configs)
    print(f"Total calls (L0_user only): {total_calls}")
    print(f"Estimated cost: ${grand:.2f}\n")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set; aborting.")
        return

    # Verify the render produces the expected structure
    sample_assignment = {
        "user_persona": "left",
        "claude_priming": "republican-primed",
        "depth": "thorough",
        "instruction": "L0_user",
    }
    test_sys, test_user = cbe.render(configs[0], configs[0].questions[0], sample_assignment)
    print("=== Sample L0_user render: system prompt should NOT have L0 prefix ===")
    print(test_sys[:200])
    print()
    print("=== Sample L0_user render: user prompt SHOULD start with L0 prefix ===")
    print(test_user[:300])
    print()

    all_rows: list[dict] = []
    for cfg in configs:
        print(f"=== {cfg.name} ===")
        rows = await run(cfg)
        all_rows.extend(rows)

    out_path = Path(__file__).resolve().parent / "persona_l0_placement_rows.json"
    out_path.write_text(json.dumps(all_rows, indent=2, default=str))

    # Three-way comparison table.
    prior = _load_system_baseline_data()
    print("\n" + "=" * 100)
    print("THREE-WAY COMPARISON: baseline | L0_system | L0_user (gap = right - left)")
    print("=" * 100)
    header = f"{'cell':<55} {'condition':<10} {'left':>6} {'mod':>6} {'unsp':>6} {'right':>6} {'gap':>6}"
    print(header)
    print("-" * len(header))
    for cand_id, priming, depth in TARGET_CELLS:
        # baseline + L0_system from prior data
        for cond_label, prior_cond in (("baseline", "baseline"), ("L0_system", "L0")):
            means = {}
            for persona in ("left", "moderate", "unspecified", "right"):
                vals = prior.get((cand_id, priming, depth, prior_cond, persona), [])
                if vals:
                    means[persona] = sum(vals) / len(vals)
            if "left" in means and "right" in means:
                gap = means["right"] - means["left"]
                cell_label = f"{cand_id}|{priming}|{depth}"
                print(
                    f"{cell_label:<55} {cond_label:<10} "
                    f"{means.get('left', float('nan')):>6.2f} "
                    f"{means.get('moderate', float('nan')):>6.2f} "
                    f"{means.get('unspecified', float('nan')):>6.2f} "
                    f"{means.get('right', float('nan')):>6.2f} "
                    f"{gap:>+6.2f}"
                )
        # L0_user from current run
        cur_means = {}
        for persona in ("left", "moderate", "unspecified", "right"):
            xs = [
                r["rating"]
                for r in all_rows
                if r["question_id"] == cand_id
                and r["claude_priming"] == priming
                and r["depth"] == depth
                and r["user_persona"] == persona
                and r["rating"] is not None
            ]
            if xs:
                cur_means[persona] = sum(xs) / len(xs)
        if "left" in cur_means and "right" in cur_means:
            gap = cur_means["right"] - cur_means["left"]
            cell_label = f"{cand_id}|{priming}|{depth}"
            print(
                f"{cell_label:<55} {'L0_user':<10} "
                f"{cur_means.get('left', float('nan')):>6.2f} "
                f"{cur_means.get('moderate', float('nan')):>6.2f} "
                f"{cur_means.get('unspecified', float('nan')):>6.2f} "
                f"{cur_means.get('right', float('nan')):>6.2f} "
                f"{gap:>+6.2f}"
            )
        print()

    print(f"Saved {len(all_rows)} rows -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main_async())
