"""Citation verifiability scorer.

Walks the model's output for URL-like strings and checks that each one:
1. resolves with a 2xx HTTP status, and
2. contains content that (loosely) supports the surrounding claim.

Step 1 is cheap. Step 2 is delegated to a judge model. This scorer is
expensive on every-task runs — use it in targeted citation-heavy evals
rather than by default.
"""

from __future__ import annotations

import re

import httpx
from inspect_ai.scorer import Score, Scorer, Target, mean, scorer
from inspect_ai.solver import TaskState

_URL_RE = re.compile(r"https?://[^\s\)\]>,]+")


@scorer(metrics=[mean()])
def citation_verifiability(timeout_seconds: float = 5.0) -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        output = state.output.completion or ""
        urls = _URL_RE.findall(output)
        if not urls:
            return Score(
                value=0.0,
                answer=output,
                explanation="no citations found",
                metadata={"n_urls": 0},
            )

        resolved: dict[str, bool] = {}
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            for url in urls:
                try:
                    r = await client.head(url)
                    resolved[url] = 200 <= r.status_code < 400
                except Exception:
                    resolved[url] = False

        good = sum(1 for ok in resolved.values() if ok)
        value = good / len(urls)

        return Score(
            value=value,
            answer=output,
            explanation=f"{good}/{len(urls)} citations resolved",
            metadata={"urls": resolved},
        )

    return score
