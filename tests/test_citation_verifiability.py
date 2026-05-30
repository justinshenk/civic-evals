"""citation_verifiability scorer — URL-resolution path with mocked HTTP.

The scorer is now in the production ``__all__`` (used by the search-enabled
``policy_impact_personalization`` variant), so it needs an offline test
that doesn't hit the network. We mock ``httpx.AsyncClient`` so CI runs
the same code path without any DNS or HTTP calls.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Self

import pytest


class _StubTarget:
    pass


def _state(completion: str) -> SimpleNamespace:
    return SimpleNamespace(
        output=SimpleNamespace(completion=completion),
        metadata={},
    )


class _MockResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _MockClient:
    """Returns prearranged status codes per URL; raises for unknown URLs.

    Async-context-manager so ``async with httpx.AsyncClient(...)`` works.
    """

    def __init__(self, status_by_url: dict[str, int], raise_for: set[str] | None = None) -> None:
        self._status = status_by_url
        self._raise = raise_for or set()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def head(self, url: str) -> _MockResponse:
        if url in self._raise:
            raise RuntimeError("simulated network failure")
        return _MockResponse(self._status.get(url, 404))


@pytest.fixture
def patch_httpx(monkeypatch: pytest.MonkeyPatch):
    def install(status_by_url: dict[str, int], raise_for: set[str] | None = None):
        def factory(*_a: Any, **_k: Any) -> _MockClient:
            return _MockClient(status_by_url, raise_for)

        # citation.py does ``async with httpx.AsyncClient(...) as client:``
        import sys
        mod = sys.modules["p3.scorers.citation"]
        monkeypatch.setattr(mod.httpx, "AsyncClient", factory)
    return install


@pytest.mark.asyncio
async def test_no_urls_scores_zero(patch_httpx) -> None:
    from p3.scorers.citation import citation_verifiability

    patch_httpx({})
    score = await citation_verifiability()(_state("No links here."), _StubTarget())  # type: ignore[arg-type]
    assert score.value == 0.0
    assert score.metadata["n_urls"] == 0
    assert "no citations" in score.explanation.lower()


@pytest.mark.asyncio
async def test_all_urls_resolve(patch_httpx) -> None:
    from p3.scorers.citation import citation_verifiability

    completion = (
        "See https://www.eac.gov/voters and https://www.fvap.gov/ for details."
    )
    patch_httpx({
        "https://www.eac.gov/voters": 200,
        "https://www.fvap.gov/": 301,  # redirect; httpx follows so 2xx-or-3xx counts
    })
    score = await citation_verifiability()(_state(completion), _StubTarget())  # type: ignore[arg-type]
    assert score.value == 1.0
    assert "2/2" in score.explanation


@pytest.mark.asyncio
async def test_mixed_resolution(patch_httpx) -> None:
    from p3.scorers.citation import citation_verifiability

    completion = "Sources: https://good.example/page and https://broken.example/404"
    patch_httpx({
        "https://good.example/page": 200,
        "https://broken.example/404": 404,
    })
    score = await citation_verifiability()(_state(completion), _StubTarget())  # type: ignore[arg-type]
    assert score.value == 0.5  # 1/2


@pytest.mark.asyncio
async def test_network_failure_counts_as_unresolved(patch_httpx) -> None:
    from p3.scorers.citation import citation_verifiability

    completion = "Citation: https://flaky.example/page"
    patch_httpx({}, raise_for={"https://flaky.example/page"})
    score = await citation_verifiability()(_state(completion), _StubTarget())  # type: ignore[arg-type]
    assert score.value == 0.0
    assert score.metadata["urls"]["https://flaky.example/page"] is False
