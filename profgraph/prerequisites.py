"""UTD CS prerequisite knowledge graph.

Hardcoded from the UTD CS degree plan. Updated for 2025-2026 catalog.
Phase 3 will scrape course catalogs for multi-university support.
"""

from __future__ import annotations

# prerequisite -> list of courses it unlocks
# Format: "CS XXXX": ["CS YYYY", "CS ZZZZ"]
UTD_CS_PREREQS: dict[str, list[str]] = {
    # Foundation
    "CS 1336": ["CS 1337"],
    "CS 1337": ["CS 2305", "CS 2336"],
    "CS 2305": ["CS 3305", "CS 3341", "CS 3345", "CS 4349"],
    "CS 2336": ["CS 2340", "CS 3345"],

    # Core
    "CS 2340": ["CS 4347", "CS 4348", "CS 4349"],
    "CS 3305": ["CS 4348", "CS 4349", "CS 4375"],
    "CS 3341": [],
    "CS 3345": ["CS 4348", "CS 4349", "CS 4375", "CS 4376"],

    # Upper division
    "CS 4141": [],
    "CS 4337": [],
    "CS 4341": [],
    "CS 4347": [],
    "CS 4348": [],
    "CS 4349": [],
    "CS 4365": ["CS 4375"],
    "CS 4375": [],
    "CS 4376": [],
    "CS 4384": [],
    "CS 4386": [],
    "CS 4389": [],
    "CS 4390": [],
    "CS 4391": [],
    "CS 4392": [],
    "CS 4393": [],
    "CS 4394": [],
    "CS 4395": [],
    "CS 4396": [],
    "CS 4397": [],
    "CS 4398": [],
    "CS 4399": [],

    # Math/Science prerequisites for CS courses
    "MATH 2413": ["MATH 2414", "CS 3341"],
    "MATH 2414": ["MATH 2418"],
    "MATH 2418": ["CS 3305"],
}


def _build_reverse_map() -> dict[str, list[str]]:
    """Build course -> prerequisites mapping (reverse of UTD_CS_PREREQS)."""
    result: dict[str, list[str]] = {}
    for prereq, unlocks in UTD_CS_PREREQS.items():
        for course in unlocks:
            result.setdefault(course, []).append(prereq)
    return result


_REVERSE_PREREQS = _build_reverse_map()


def get_prerequisites(course: str, depth: int = 1) -> dict:
    """Get prerequisites for a course, optionally traversing depth levels.

    Args:
        course: Course code (e.g. "CS 3345").
        depth: How many levels deep to traverse (1 = direct prereqs only).

    Returns:
        Dict with 'course', 'prerequisites' (list), and 'tree' (nested).
    """
    course = course.upper().strip()

    def _traverse(c: str, d: int) -> dict:
        prereqs = _REVERSE_PREREQS.get(c, [])
        node = {"course": c, "prerequisites": prereqs}
        if d > 1 and prereqs:
            node["children"] = [_traverse(p, d - 1) for p in prereqs]
        return node

    return _traverse(course, depth)


def get_unlocks(course: str) -> list[str]:
    """Get courses that this course is a prerequisite for."""
    return UTD_CS_PREREQS.get(course.upper().strip(), [])


def get_all_courses() -> list[str]:
    """Get all courses in the prerequisite graph."""
    courses: set[str] = set()
    for prereq, unlocks in UTD_CS_PREREQS.items():
        courses.add(prereq)
        courses.update(unlocks)
    return sorted(courses)
