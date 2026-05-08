"""Edge cases for the bias-templates rating parser and renderer.

The parser is the single point of failure between API output and the
OLS regression — a missed parse silently drops a rating from the
factorial cell, which can bias the coefficient estimates if missingness
correlates with the protected factors.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# bias_templates lives in analysis/, which isn't a package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from bias_templates import (  # noqa: E402
    FACTORIAL_EXPERIENCE,
    FACTORIAL_PACKAGES,
    FACTORIAL_PARTIES,
    FACTORIAL_RIGOR,
    SCHOOL_BOARD_SCENARIO,
    parse_rating,
    render_profile,
)

# ---- parse_rating --------------------------------------------------------

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Some discussion.\n\nRATING: 7", 7.0),
        ("RATING: 1", 1.0),
        ("RATING: 10", 10.0),
        ("Reasoning...\nRATING:7.5", 7.5),         # decimals, no space
        ("RATING:  7  trailing junk", 7.0),         # extra spaces, junk after
        ("rating: 5", 5.0),                         # case-insensitive
    ],
)
def test_parse_rating_valid(text: str, expected: float) -> None:
    assert parse_rating(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "Some discussion with no rating line at all.",
        "RATING: 0",        # below 1
        "RATING: 11",       # above 10
        "RATING: -3",       # negative
        "RATING: abc",      # non-numeric
    ],
)
def test_parse_rating_invalid_returns_none(text: str) -> None:
    assert parse_rating(text) is None


def test_parse_rating_takes_first_when_multiple() -> None:
    """If a model emits two RATING: lines, take the first match.

    Locks in current behavior so a future regex change doesn't silently
    flip which rating gets attributed to a cell."""
    assert parse_rating("RATING: 4\n... RATING: 9") == 4.0


def test_parse_rating_handles_none_input() -> None:
    """The driver passes ``text or ""`` so this shouldn't fire in practice,
    but the parser's contract is that empty/falsy input returns None."""
    assert parse_rating(None) is None  # type: ignore[arg-type]


# ---- render_profile ------------------------------------------------------

def test_render_profile_includes_every_factor_value() -> None:
    """The rendered prompt must mention every factorial value passed in.

    A renderer that drops a factor would make the OLS coefficient on that
    factor go to zero — silently — without anyone noticing in a hand-eyeball
    of one cell."""
    profile = render_profile(
        SCHOOL_BOARD_SCENARIO,
        party="Republican",
        package="R-typical",
        experience="senior",
        rigor="deep",
    )
    assert "Republican" in profile
    assert "Senior" in profile  # capitalize() in the renderer
    assert "Sixteen years" in profile  # senior experience blurb
    # R-typical deep platform names a specific bill.
    assert "SB 412" in profile
    assert "RATING:" in profile  # output contract reminder


def test_render_profile_all_cells_unique() -> None:
    """Every (party, package, experience, rigor) cell must produce a unique
    string — otherwise the factorial collapses on duplicates and the model
    gets the same prompt for two distinct cells."""
    seen: set[str] = set()
    for party in FACTORIAL_PARTIES:
        for package in FACTORIAL_PACKAGES:
            for exp in FACTORIAL_EXPERIENCE:
                for rig in FACTORIAL_RIGOR:
                    p = render_profile(SCHOOL_BOARD_SCENARIO, party, package, exp, rig)
                    assert p not in seen, f"duplicate prompt for ({party}, {package}, {exp}, {rig})"
                    seen.add(p)
    assert len(seen) == 24  # 2 x 2 x 3 x 2
