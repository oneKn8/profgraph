"""University registry for ProfGraph.

Maps university identifiers to RMP school IDs and grade data adapters.
Phase 3: pluggable architecture for multi-university support.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class University:
    """University metadata."""

    key: str
    name: str
    rmp_school_id: str
    grade_source: str  # "nebula" | "none" (more adapters in future)
    state: str = ""
    city: str = ""


# Registry of supported universities
UNIVERSITIES: dict[str, University] = {
    "utd": University(
        key="utd",
        name="University of Texas at Dallas",
        rmp_school_id="U2Nob29sLTEyNzM=",
        grade_source="nebula",
        state="TX", city="Richardson",
    ),
    "tamu": University(
        key="tamu",
        name="Texas A&M University",
        rmp_school_id="U2Nob29sLTEwMDM=",
        grade_source="none",
        state="TX", city="College Station",
    ),
    "utaustin": University(
        key="utaustin",
        name="University of Texas at Austin",
        rmp_school_id="U2Nob29sLTEyNTU=",
        grade_source="none",
        state="TX", city="Austin",
    ),
    "uta": University(
        key="uta",
        name="University of Texas at Arlington",
        rmp_school_id="U2Nob29sLTEzNDM=",
        grade_source="none",
        state="TX", city="Arlington",
    ),
    "uh": University(
        key="uh",
        name="University of Houston",
        rmp_school_id="U2Nob29sLTExMDk=",
        grade_source="none",
        state="TX", city="Houston",
    ),
    "rice": University(
        key="rice",
        name="Rice University",
        rmp_school_id="U2Nob29sLTc5OQ==",
        grade_source="none",
        state="TX", city="Houston",
    ),
    "unt": University(
        key="unt",
        name="University of North Texas",
        rmp_school_id="U2Nob29sLTEyNTI=",
        grade_source="none",
        state="TX", city="Denton",
    ),
}

# Common aliases for university names
ALIASES: dict[str, str] = {
    "ut dallas": "utd",
    "university of texas at dallas": "utd",
    "texas a&m": "tamu",
    "texas a&m university": "tamu",
    "texas am": "tamu",
    "a&m": "tamu",
    "ut austin": "utaustin",
    "university of texas at austin": "utaustin",
    "university of texas": "utaustin",
    "ut arlington": "uta",
    "university of texas at arlington": "uta",
    "university of houston": "uh",
    "u of h": "uh",
    "rice university": "rice",
    "university of north texas": "unt",
}


def resolve(university: str) -> University:
    """Resolve a university identifier or name to a University object.

    Args:
        university: Key like 'utd' or name like 'University of Texas at Dallas'.

    Returns:
        University object.

    Raises:
        ValueError: If the university is not supported.
    """
    key = university.lower().strip()
    key = ALIASES.get(key, key)
    if key in UNIVERSITIES:
        return UNIVERSITIES[key]
    raise ValueError(
        f"University '{university}' not supported. "
        f"Available: {', '.join(sorted(UNIVERSITIES))}"
    )


def list_supported() -> list[University]:
    """Return all supported universities."""
    return list(UNIVERSITIES.values())
