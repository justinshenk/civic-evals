"""General driver for persona-belief sycophancy runs.

Usage:
    python analysis/run_sycophancy.py <topic> <condition> [provider]
      topic     : immigration | healthcare
      condition : baseline | l0
      provider  : anthropic (default) | openrouter

Runs the 6-persona x 15-question x 3-rep factorial for the chosen topic,
optionally with the L0 fairness prefix. Subject = Haiku, judge = Sonnet.
Saves rows to:
    analysis/sycophancy_<topic>_<condition>_rows.json
and prints the pooled + per-question slopes.

Provider note: defaults to the direct Anthropic API (uses
ANTHROPIC_API_KEY). The OpenRouter path is kept for cross-provider
runs but requires OPENROUTER_API_KEY with credits.

Data is persisted IMMEDIATELY after collection, before any analysis
print, so a formatting bug can't cost the API spend. Subject/judge
errors are surfaced in the parse-rate line so credit/rate-limit
failures are caught immediately.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.stats as stats
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")
sys.path.insert(0, str(REPO_ROOT / "analysis"))

from sycophancy_configs import (  # noqa: E402
    PERSONA_ORDER,
    TOPICS,
    build_judge_prompt,
    build_system_prompt,
)

# Model IDs differ by provider.
MODELS = {
    "anthropic": {"subject": "claude-haiku-4-5", "judge": "claude-sonnet-4-6"},
    "openrouter": {"subject": "anthropic/claude-haiku-4.5", "judge": "anthropic/claude-sonnet-4.5"},
}
N_REPS = 3
CONCURRENCY = 8
SUBJECT_MAX_TOKENS = 1024
JUDGE_MAX_TOKENS = 320

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_judge(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_RE.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


class Backend:
    """Thin async wrapper over either the Anthropic SDK or OpenRouter."""

    def __init__(self, provider: str):
        self.provider = provider
        self.models = MODELS[provider]
        if provider == "anthropic":
            from anthropic import AsyncAnthropic

            key = os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY missing from environment / .env")
            self._client = AsyncAnthropic(api_key=key)
        elif provider == "openrouter":
            from openai import AsyncOpenAI

            key = os.environ.get("OPENROUTER_API_KEY")
            if not key:
                raise RuntimeError("OPENROUTER_API_KEY missing from environment / .env")
            self._client = AsyncOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")
        else:
            raise ValueError(f"unknown provider {provider!r}")

    async def _anthropic_call(self, model, max_tokens, system, user) -> str:
        kwargs: dict = {"model": model, "max_tokens": max_tokens,
                        "messages": [{"role": "user", "content": user}]}
        if system:
            kwargs["system"] = system
        resp = await self._client.messages.create(**kwargs)
        return "".join(getattr(b, "text", "") for b in resp.content if hasattr(b, "text"))

    async def _openrouter_call(self, model, max_tokens, system, user) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        resp = await self._client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=messages
        )
        return (resp.choices[0].message.content or "") if resp.choices else ""

    async def call(self, model, max_tokens, system, user) -> str:
        if self.provider == "anthropic":
            return await self._anthropic_call(model, max_tokens, system, user)
        return await self._openrouter_call(model, max_tokens, system, user)


async def subject_call(backend: Backend, system_prompt, user_prompt):
    try:
        return await backend.call(backend.models["subject"], SUBJECT_MAX_TOKENS,
                                  system_prompt, user_prompt)
    except Exception as e:
        return f"<error: {type(e).__name__}: {e}>"


async def judge_call(backend: Backend, prompt):
    try:
        text = await backend.call(backend.models["judge"], JUDGE_MAX_TOKENS, "", prompt)
        return parse_judge(text), text
    except Exception as e:
        return None, f"<error: {type(e).__name__}: {e}>"


@dataclass
class Row:
    topic: str
    condition: str
    persona_key: str
    persona_ordinal: float | None
    persona_description: str
    question_id: str
    user_question: str
    rep: int
    response_text: str
    judge_scores: dict | None
    judge_text: str


async def main_async(topic_key: str, condition: str, provider: str = "anthropic") -> None:
    topic = TOPICS[topic_key]
    l0 = condition == "l0"
    n = len(topic.personas) * len(topic.questions) * N_REPS
    print(f"Topic: {topic.label} | condition: {condition} | provider: {provider} | "
          f"subject+judge calls: {n} each")

    backend = Backend(provider)
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one_cell(persona_key, persona_desc, ordinal, q_id, q_text, rep) -> Row:
        async with sem:
            sys_prompt = build_system_prompt(persona_desc, l0=l0)
            response = await subject_call(backend, sys_prompt, q_text)
            judge_prompt = build_judge_prompt(topic, persona_desc, q_text, response)
            scores, judge_text = await judge_call(backend, judge_prompt)
            return Row(
                topic=topic_key, condition=condition, persona_key=persona_key,
                persona_ordinal=ordinal, persona_description=persona_desc,
                question_id=q_id, user_question=q_text, rep=rep,
                response_text=response, judge_scores=scores, judge_text=judge_text,
            )

    coros = []
    for persona_key, (ordinal, desc) in topic.personas.items():
        for q_id, q_text in topic.questions:
            for rep in range(N_REPS):
                coros.append(one_cell(persona_key, desc, ordinal, q_id, q_text, rep))

    print(f"Dispatching {len(coros)} cells ...")
    rows = await asyncio.gather(*coros)
    parsed = sum(1 for r in rows if r.judge_scores)
    subj_err = sum(1 for r in rows if r.response_text.startswith("<error"))
    print(f"Got {len(rows)} rows; judge-parsed: {parsed}; subject-errors: {subj_err}")

    # PERSIST FIRST.
    out_path = REPO_ROOT / "analysis" / f"sycophancy_{topic_key}_{condition}_rows.json"
    out_path.write_text(json.dumps([r.__dict__ for r in rows], indent=2, default=str))
    print(f"Saved -> {out_path.name}")

    # Guard: if more than 10% of calls failed, flag loudly — likely an
    # exhausted-credit or rate-limit situation, results not trustworthy.
    if parsed < 0.9 * len(rows) or subj_err > 0.1 * len(rows):
        print(f"\n!!! HIGH FAILURE RATE: parsed {parsed}/{len(rows)}, "
              f"subject errors {subj_err}/{len(rows)}. "
              f"Sample error: "
              f"{next((r.judge_text for r in rows if r.judge_scores is None), '')[:120]}")
        print("!!! Results below are NOT trustworthy. Fix the API budget and re-run.\n")

    # Pooled slope (exclude unspecified control which has no ordinal).
    xs = [r.persona_ordinal for r in rows if r.persona_ordinal is not None and r.judge_scores]
    ys = [r.judge_scores["policy_lean"] for r in rows
          if r.persona_ordinal is not None and r.judge_scores and "policy_lean" in r.judge_scores]
    # align xs and ys
    pairs = [(r.persona_ordinal, r.judge_scores["policy_lean"]) for r in rows
             if r.persona_ordinal is not None and r.judge_scores and "policy_lean" in r.judge_scores]
    xa = np.array([p[0] for p in pairs], dtype=float)
    ya = np.array([p[1] for p in pairs], dtype=float)
    res = stats.linregress(xa, ya)
    print(f"=== Pooled slope ({topic.label}, {condition}) ===")
    print(f"  slope={res.slope:+.4f}  r={res.rvalue:+.3f}  p={res.pvalue:.2e}  n={len(pairs)}")

    print("\n=== Mean policy_lean per persona ===")
    for pk in PERSONA_ORDER:
        vals = [r.judge_scores["policy_lean"] for r in rows
                if r.persona_key == pk and r.judge_scores and "policy_lean" in r.judge_scores]
        if vals:
            print(f"  {pk:<15} n={len(vals):<3} mean={np.mean(vals):+6.2f}  sd={np.std(vals):.2f}")


if __name__ == "__main__":
    topic_arg = sys.argv[1] if len(sys.argv) > 1 else "immigration"
    cond_arg = sys.argv[2] if len(sys.argv) > 2 else "baseline"
    provider_arg = sys.argv[3] if len(sys.argv) > 3 else "anthropic"
    asyncio.run(main_async(topic_arg, cond_arg, provider_arg))
