"""LLM judge: did this completion acknowledge training-data staleness or
hedge toward an authoritative source?

Replaces an earlier regex-based heuristic (curated phrase list) with a
single judge call per failed completion. Phrase lists go stale as model
output styles drift; an LLM judge generalizes across paraphrases without
manual maintenance.

Scope decisions:

- Runs at *rollup* time, not at eval time. The check only matters for
  rows already classified as failures (small population, ~tens) so we
  don't pay it on every passing sample. The verdict is written into the
  rollup JSON the site reads.
- Skips ``*_with_search`` evals — search-enabled variants should cite a
  fresh URL, not hedge on cutoff. ``citation_verifiability`` covers them.
- Disk-cached by ``sha256(eval || task_id || completion)`` so repeated
  rollups against unchanged logs don't re-call the judge. Cache file is
  gitignored.
- Uses ``CI_SMOKE_MODEL`` (Haiku) by default — the cheapest provider in
  the suite. Override via ``judge_model`` argument for ablation.
- If ``ANTHROPIC_API_KEY`` is unset (or whatever provider the chosen
  judge requires), the function logs a one-line warning and returns
  ``None`` verdicts so CI offline runs and missing-key environments
  degrade gracefully instead of crashing the rollup.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StalenessVerdict:
    """Result of one judge call. ``acknowledged is None`` when the row
    couldn't be judged (search-enabled eval, missing API key, judge crash)."""

    acknowledged: bool | None
    kind: str | None  # "cutoff" | "source" | "variation" | "none" | None
    evidence: str | None  # short quote/paraphrase from the response

    def to_dict(self) -> dict[str, Any]:
        return {
            "acknowledged_staleness": self.acknowledged,
            "staleness_kind": self.kind,
            "staleness_evidence": self.evidence,
        }


_CACHE_PATH = Path(__file__).resolve().parent / ".staleness_cache.json"


_JUDGE_PROMPT = """You are auditing a model response that was scored as wrong on a civic-information question.

Your only job is to decide whether the response acknowledged that the model's
information could be out of date OR pointed the asker at an authoritative
source for verification. This is the "knew it didn't know" signal.

Return ONLY valid JSON in this exact shape (no prose, no markdown fences):

{{
  "acknowledged": true|false,
  "kind": "cutoff" | "source" | "variation" | "none",
  "evidence": "short quote (≤ 20 words) from the response that justifies the verdict, or empty string"
}}

Decision rules:

- "cutoff": the response mentions training cutoff, knowledge cutoff, training
  data, that information may be outdated, that it can't access real-time data,
  or anything else that names training-data staleness. Set acknowledged=true.
- "source": the response directs the asker to a specific authoritative source
  (Secretary of State, election office, EAC, NCSL, NASS, a state lawyer,
  a state-government website, etc.). Set acknowledged=true.
- "variation": the response names jurisdictional variation as a reason to
  verify (e.g., "rules vary by state", "depends on your state"). Set
  acknowledged=true.
- "none": the response is confident with no caveat about staleness, source,
  or variation. Generic refusals ("I cannot help with that") are NOT a
  staleness hedge — set acknowledged=false, kind="none".

If multiple kinds apply, pick the strongest (cutoff > source > variation).

Question that was asked:
{question}

Model response:
{response}
"""


def _hash(eval_name: str, task_id: str, completion: str) -> str:
    h = hashlib.sha256()
    h.update(eval_name.encode())
    h.update(b"\x00")
    h.update(task_id.encode())
    h.update(b"\x00")
    h.update(completion.encode())
    return h.hexdigest()


def _load_cache(path: Path = _CACHE_PATH) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        # Corrupt cache shouldn't block the rollup; rebuild from scratch.
        return {}


def _save_cache(cache: dict[str, dict[str, Any]], path: Path = _CACHE_PATH) -> None:
    try:
        # Atomic write via sibling tmp, same pattern as rollup._atomic_write_text.
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(cache, indent=2))
        tmp.replace(path)
    except OSError as e:  # disk full, permissions — don't crash the rollup
        logger.warning("staleness cache save failed: %s", e)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse(text: str) -> dict[str, Any]:
    """Tolerate prose-wrapped JSON; same pattern as rubric_judge."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_RE.search(text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def _verdict_from_judge(parsed: dict[str, Any]) -> StalenessVerdict:
    ack = parsed.get("acknowledged")
    if not isinstance(ack, bool):
        return StalenessVerdict(None, None, None)
    kind_raw = parsed.get("kind")
    kind = kind_raw if kind_raw in {"cutoff", "source", "variation", "none"} else "none"
    evidence_raw = parsed.get("evidence", "")
    evidence = evidence_raw if isinstance(evidence_raw, str) else ""
    # Trim excessively long quotes — judge sometimes returns the whole response.
    if len(evidence) > 200:
        evidence = evidence[:197].rstrip() + "…"
    return StalenessVerdict(ack, kind, evidence or None)


def is_search_eval(eval_name: str | None) -> bool:
    """Search-enabled task variants are expected to cite, not hedge."""
    return bool(eval_name) and eval_name.endswith("_with_search")


async def _judge_one(
    *, question: str, response: str, judge_model: str
) -> StalenessVerdict:
    """One judge call. Imports inspect-ai lazily so rollup.py can be loaded
    in environments without inspect-ai installed (e.g. analysis-only setups).
    """
    from inspect_ai.model import ChatMessageUser, get_model

    try:
        out = await get_model(judge_model).generate(
            [ChatMessageUser(content=_JUDGE_PROMPT.format(
                question=question, response=response,
            ))]
        )
    except Exception as e:  # network, auth, model crash — don't kill the rollup
        logger.warning("staleness judge call failed: %s", e)
        return StalenessVerdict(None, None, None)
    return _verdict_from_judge(_parse(out.completion))


def judge_failures(
    failures: list[dict[str, Any]],
    *,
    judge_model: str | None = None,
    cache_path: Path = _CACHE_PATH,
) -> list[dict[str, Any]]:
    """Mutate ``failures`` in place, attaching staleness verdicts.

    Skips rows where the eval is search-enabled (verdict stays ``None``).
    Skips entirely if the judge's API key isn't set, returning ``None``
    verdicts so the rollup degrades gracefully. Reads/writes a JSON
    cache so reruns over unchanged completions are free.

    Returns the same list for chainability.
    """
    if not failures:
        return failures

    judge = judge_model or _default_judge()
    if not _has_key_for(judge):
        logger.warning(
            "staleness judge skipped: no API key for %s; "
            "verdicts will be null. Set the relevant key to enable.",
            judge,
        )
        for f in failures:
            f.setdefault("acknowledged_staleness", None)
            f.setdefault("staleness_kind", None)
            f.setdefault("staleness_evidence", None)
        return failures

    cache = _load_cache(cache_path)
    pending: list[tuple[int, str]] = []  # (index, cache_key)
    for i, f in enumerate(failures):
        eval_name = f.get("eval") or ""
        if is_search_eval(eval_name):
            f["acknowledged_staleness"] = None
            f["staleness_kind"] = None
            f["staleness_evidence"] = None
            continue
        key = _hash(eval_name, str(f.get("task_id", "")), f.get("completion") or "")
        cached = cache.get(key)
        if cached is not None:
            f.update(cached)
            continue
        pending.append((i, key))

    if pending:
        # Question text isn't in the failures list — best-effort fall back to
        # task_id as a stand-in. The judge mostly looks at the response.
        async def _run_all() -> list[StalenessVerdict]:
            return await asyncio.gather(*(
                _judge_one(
                    question=str(failures[i].get("task_id") or ""),
                    response=failures[i].get("completion") or "",
                    judge_model=judge,
                )
                for i, _ in pending
            ))

        verdicts = asyncio.run(_run_all())
        for (i, key), verdict in zip(pending, verdicts, strict=True):
            payload = verdict.to_dict()
            failures[i].update(payload)
            if verdict.acknowledged is not None:  # only cache real verdicts
                cache[key] = payload

        _save_cache(cache, cache_path)

    return failures


def _default_judge() -> str:
    """Cheapest model in the suite; matches the CI smoke default."""
    # Avoid importing p3.providers at module load to keep this file
    # importable from minimal environments.
    return "anthropic/claude-haiku-4-5"


_PROVIDER_ENV: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "together": "TOGETHER_API_KEY",
}


def _has_key_for(model_id: str) -> bool:
    provider, _, _ = model_id.partition("/")
    env = _PROVIDER_ENV.get(provider)
    return bool(env and os.environ.get(env))
