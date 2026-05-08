"""``last_verified`` field acceptance + ISO-format guard.

The schema-level test exists to make sure new tasks can adopt this
field without ceremony, while malformed dates fail loud at load time
rather than silently rendering as broken pills on the site.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from p3.schemas import Task

_BASE = {
    "id": "x-1",
    "domain": "civics",
    "subdomain": "voting",
    "input": "a fine question",
    "target": "answer",
}


def _meta(**overrides: object) -> dict:
    return {
        "difficulty": "easy",
        "source": "src",
        "tags": ["t"],
        **overrides,
    }


def test_last_verified_optional_omitted_is_fine() -> None:
    Task.model_validate({**_BASE, "metadata": _meta()})


def test_last_verified_optional_explicit_null_is_fine() -> None:
    Task.model_validate({**_BASE, "metadata": _meta(last_verified=None)})


def test_last_verified_iso_date_accepted() -> None:
    t = Task.model_validate({**_BASE, "metadata": _meta(last_verified="2026-04-15")})
    assert t.metadata.last_verified == "2026-04-15"


def test_last_verified_non_iso_format_rejected() -> None:
    """Anything that isn't ``YYYY-MM-DD`` is rejected at parse time so
    a typo doesn't silently become a "stale" badge that's actually
    meaningless."""
    for bad in ("2026/04/15", "April 15 2026", "2026-4-5", "26-04-15", ""):
        with pytest.raises(ValidationError):
            Task.model_validate({**_BASE, "metadata": _meta(last_verified=bad)})
