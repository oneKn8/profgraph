"""ProfGraph MCP Server -- AI Professor Intelligence.

Gives any LLM instant, pre-computed professor intelligence: teaching style,
grade distributions, and student reviews. Connect via MCP to get data-backed
course recommendations instead of hallucinated guesses.
"""

from __future__ import annotations

import asyncio
import os

from mcp.server.fastmcp import FastMCP

from .cache import TTLCache
from .grades import GradesClient, GradesError
from .intel import IntelStore, IntelEntry
from .models import ProfessorProfile
from .nlp import TeachingStyle
from .prerequisites import get_prerequisites as _get_prereqs, get_unlocks
from .rmp import RMPClient, RMPError
from .universities import list_supported, resolve as resolve_university

mcp = FastMCP(
    "profgraph_mcp",
    host=os.environ.get("PROFGRAPH_HOST", "0.0.0.0"),
    port=int(os.environ.get("PROFGRAPH_PORT", "8000")),
)

_cache = TTLCache(default_ttl=86400)
_rmp = RMPClient(_cache)
_grades = GradesClient(_cache)
_intel = IntelStore()


def _parse_course(course: str) -> tuple[str, str]:
    """Parse 'CS 3341', 'CS3341', 'cs-3341' into ('CS', '3341')."""
    c = course.strip().upper().replace("-", " ").replace("_", " ")
    if " " in c:
        prefix, number = c.split(None, 1)
        return prefix, number.strip()
    i = 0
    while i < len(c) and c[i].isalpha():
        i += 1
    return c[:i], c[i:]


def _fmt_wta(pct: float | None) -> str:
    if pct is None or pct < 0:
        return "N/A"
    return f"{pct:.0f}%"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_universities() -> str:
    """List all supported universities with their identifiers.

    Use the 'key' value as the university parameter in other tools.
    Grade data availability varies by university.
    """
    unis = list_supported()
    lines = ["# Supported Universities", ""]
    for u in unis:
        grade_note = "with grade data" if u.grade_source != "none" else "professor data only"
        lines.append(f"- **{u.key}**: {u.name} ({u.city}, {u.state}) -- {grade_note}")
    lines.extend([
        "",
        "All universities support professor search, profiles, comparisons, "
        "and recommendations. Grade distributions are currently available for UTD only.",
    ])
    return "\n".join(lines)


@mcp.tool()
async def search_professors(
    university: str,
    query: str,
    department: str | None = None,
) -> str:
    """Search for professors at a university by name.

    Returns matching professors with their overall rating, difficulty score,
    would-take-again percentage, and total review count. Use professor names
    from these results with get_professor_profile for detailed information.

    Args:
        university: University identifier (e.g. 'utd' for UT Dallas).
        query: Professor name or partial name to search for.
        department: Optional department filter (e.g. 'Computer Science').
    """
    try:
        results = await _rmp.search(university, query)
    except (RMPError, GradesError) as e:
        return f"Error: {e}"

    if department:
        dept_lower = department.lower()
        results = [p for p in results if dept_lower in p.department.lower()]

    if not results:
        extra = f" in {department}" if department else ""
        return f"No professors found matching '{query}'{extra} at {university.upper()}"

    lines = [f"# Professors matching '{query}' at {university.upper()}", ""]
    for p in results:
        lines.extend([
            f"## {p.first_name} {p.last_name}",
            f"- Department: {p.department}",
            f"- Rating: {p.avg_rating}/5 | Difficulty: {p.avg_difficulty}/5",
            f"- Would Take Again: {_fmt_wta(p.would_take_again)} | Reviews: {p.num_ratings}",
            "",
        ])
    return "\n".join(lines)


@mcp.tool()
async def get_professor_profile(university: str, professor: str) -> str:
    """Get a detailed professor profile including ratings, teaching style tags,
    courses taught, and recent student reviews.

    Searches for the professor first, then fetches their full RMP profile.
    Teaching style tags are extracted from student reviews and ranked by
    frequency -- they reveal patterns like 'Tough grader', 'Lots of homework',
    or 'Amazing lectures'.

    If multiple professors match the name, the best match is used and
    alternatives are listed. Use search_professors first for precise control.

    Args:
        university: University identifier (e.g. 'utd').
        professor: Professor name to look up.
    """
    try:
        results = await _rmp.search(university, professor)
    except (RMPError, GradesError) as e:
        return f"Error: {e}"

    if not results:
        return f"Professor '{professor}' not found at {university.upper()}"

    # Disambiguation: note if multiple matches
    disambig = ""
    if len(results) > 1:
        others = ", ".join(
            f"{p.first_name} {p.last_name} ({p.department})"
            for p in results[1:4]
        )
        disambig = (
            f"\n> Note: Showing top match. Other matches: {others}. "
            "Use search_professors for the full list.\n"
        )

    try:
        prof = await _rmp.profile(results[0].rmp_id)
    except (RMPError, GradesError) as e:
        return f"Error fetching profile: {e}"

    lines = [
        f"# {prof.first_name} {prof.last_name}",
        f"{prof.department} | {university.upper()}",
    ]
    if disambig:
        lines.append(disambig)

    lines.extend([
        "",
        "## Ratings",
        f"- Overall: {prof.avg_rating}/5",
        f"- Difficulty: {prof.avg_difficulty}/5",
        f"- Would Take Again: {_fmt_wta(prof.would_take_again)}",
        f"- Total Reviews: {prof.num_ratings}",
        "",
    ])

    if prof.tags:
        lines.append("## Teaching Style Tags")
        for name, count in prof.tags[:12]:
            lines.append(f"- {name} ({count}x)")
        lines.append("")

    ts = prof.teaching_style
    if isinstance(ts, TeachingStyle):
        lines.append("## Teaching Style (NLP-extracted)")
        for label, val in [
            ("Exam Style", ts.exam_style),
            ("Homework Load", ts.homework_load),
            ("Lecture Quality", ts.lecture_quality),
            ("Curve Likelihood", ts.curve_likelihood),
            ("Accessibility", ts.accessibility),
        ]:
            if val and val != "unknown":
                lines.append(f"- {label}: {val}")
        for label, val in [
            ("Uses Textbook", ts.uses_textbook),
            ("Records Lectures", ts.records_lectures),
            ("Practice Exams", ts.provides_practice_exams),
        ]:
            if val is not None:
                lines.append(f"- {label}: {'yes' if val else 'no'}")
        if ts.warnings:
            lines.append("")
            lines.append("### Warnings")
            for w in ts.warnings:
                lines.append(f"- {w}")
        if ts.best_for:
            lines.append("")
            lines.append(f"**Best for**: {', '.join(ts.best_for)}")
        if ts.worst_for:
            lines.append(f"**Challenging for**: {', '.join(ts.worst_for)}")
        lines.append("")

    if prof.courses:
        lines.append("## Courses Taught")
        for name, count in prof.courses:
            lines.append(f"- {name} ({count} reviews)")
        lines.append("")

    if prof.reviews:
        lines.append("## Recent Reviews")
        for r in prof.reviews[:8]:
            cls = r.get("class", "N/A")
            date = r.get("date", "")
            online = " [ONLINE]" if r.get("online") else ""
            grade = ""
            if r.get("grade") and r["grade"] not in ("Not sure yet", "Rather not say"):
                grade = f" | Grade: {r['grade']}"
            lines.extend([
                f"### {cls} ({date}){online}",
                f"Quality: {r.get('quality')}/5 | "
                f"Clarity: {r.get('clarity')}/5 | "
                f"Difficulty: {r.get('difficulty')}/5{grade}",
            ])
            if r.get("tags"):
                lines.append(f"Tags: {r['tags']}")
            if r.get("comment"):
                lines.append(f"> {r['comment']}")
            lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_grade_distribution(
    university: str,
    course: str,
    professor: str | None = None,
    semester: str | None = None,
) -> str:
    """Get historical grade distributions for a course from public records.

    Returns letter grade percentages, average GPA, and total enrollment
    broken down by semester. Data comes from FOIA/TPIA public records.
    Optionally filter by professor last name or semester code.

    Args:
        university: University identifier (e.g. 'utd').
        course: Course code (e.g. 'CS 3341' or 'CS3341').
        professor: Optional professor last name to filter results.
        semester: Optional semester code to filter (e.g. '25F' for Fall 2025).
    """
    prefix, number = _parse_course(course)
    try:
        dists = await _grades.get_distribution(university, prefix, number, professor, semester)
    except (RMPError, GradesError) as e:
        return f"Error: {e}"

    if not dists:
        filters = []
        if professor:
            filters.append(f"professor: {professor}")
        if semester:
            filters.append(f"semester: {semester}")
        extra = f" ({', '.join(filters)})" if filters else ""
        return f"No grade data found for {prefix} {number}{extra}"

    total_graded = sum(d.total_graded for d in dists)
    total_all = sum(d.total for d in dists)
    total_a = sum(d.a_plus + d.a + d.a_minus for d in dists)
    total_b = sum(d.b_plus + d.b + d.b_minus for d in dists)
    total_c = sum(d.c_plus + d.c + d.c_minus for d in dists)
    total_d = sum(d.d_plus + d.d + d.d_minus for d in dists)
    total_f = sum(d.f for d in dists)
    total_w = sum(d.w for d in dists)

    overall_gpa = None
    graded_semesters = [d for d in dists if d.avg_gpa is not None]
    if graded_semesters:
        gpa_sum = sum(d.avg_gpa * d.total_graded for d in graded_semesters)
        denom = sum(d.total_graded for d in graded_semesters)
        if denom > 0:
            overall_gpa = round(gpa_sum / denom, 2)

    def pct(n: int) -> str:
        return f"{n / total_all * 100:.1f}%" if total_all else "0%"

    header = f"# Grade Distribution: {prefix} {number}"
    if professor:
        header += f" (Professor: {professor})"

    lines = [
        header,
        f"Data from {len(dists)} semesters | {total_all} total students",
        "",
        "## Overall",
    ]
    if overall_gpa is not None:
        lines.append(f"Average GPA: {overall_gpa}")
    lines.extend([
        "",
        "| Grade | % | Count |",
        "|-------|------|-------|",
        f"| A | {pct(total_a)} | {total_a} |",
        f"| B | {pct(total_b)} | {total_b} |",
        f"| C | {pct(total_c)} | {total_c} |",
        f"| D | {pct(total_d)} | {total_d} |",
        f"| F | {pct(total_f)} | {total_f} |",
        f"| W | {pct(total_w)} | {total_w} |",
        "",
        "## By Semester (recent first)",
        "",
    ])

    for d in dists[:10]:
        gpa_str = f" | GPA: {d.avg_gpa}" if d.avg_gpa is not None else ""
        lines.extend([
            f"### {d.semester_display} ({d.total} students{gpa_str})",
            f"A: {d.pct('A')}% | B: {d.pct('B')}% | C: {d.pct('C')}% | "
            f"D: {d.pct('D')}% | F: {d.pct('F')}% | W: {d.pct('W')}%",
            "",
        ])

    return "\n".join(lines)


@mcp.tool()
async def compare_professors(university: str, professors: list[str]) -> str:
    """Compare multiple professors side-by-side on ratings, difficulty,
    teaching style, and student satisfaction.

    Fetches full profiles for each professor and presents a comparison table.
    Useful for choosing between sections of the same course.

    Args:
        university: University identifier (e.g. 'utd').
        professors: List of professor names to compare (minimum 2).
    """
    if len(professors) < 2:
        return "Need at least 2 professors to compare."

    errors: dict[str, str] = {}

    async def _fetch(name: str) -> tuple[str, ProfessorProfile | None]:
        try:
            results = await _rmp.search(university, name)
            if not results:
                return name, None
            return name, await _rmp.profile(results[0].rmp_id)
        except (RMPError, GradesError) as e:
            errors[name] = str(e)
            return name, None

    fetched = await asyncio.gather(*(_fetch(n) for n in professors))
    pairs: list[tuple[str, ProfessorProfile | None]] = list(fetched)

    if not any(p for _, p in pairs):
        if errors:
            detail = "; ".join(f"{n}: {e}" for n, e in errors.items())
            return f"Could not fetch any professors. Errors: {detail}"
        return "None of the specified professors were found."

    def _header(n: str, p: ProfessorProfile | None) -> str:
        if p:
            return f"{p.first_name} {p.last_name}"
        if n in errors:
            return f"{n} (error)"
        return f"{n} (not found)"

    headers = ["Metric"] + [_header(n, p) for n, p in pairs]

    lines = [
        "# Professor Comparison",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    def _cell(p: ProfessorProfile | None, attr: str, fmt=str) -> str:
        if p is None:
            return "N/A"
        v = getattr(p, attr, None)
        if v is None:
            return "N/A"
        return fmt(v)

    rows = [
        ("Rating", "avg_rating", lambda v: f"{v}/5"),
        ("Difficulty", "avg_difficulty", lambda v: f"{v}/5"),
        ("Would Take Again", "would_take_again", _fmt_wta),
        ("Reviews", "num_ratings", str),
        ("Department", "department", str),
    ]

    for label, attr, fmt in rows:
        cells = [label] + [_cell(p, attr, fmt) for _, p in pairs]
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(["", "## Top Tags"])

    for name, prof in pairs:
        if prof and prof.tags:
            lines.append(f"### {prof.first_name} {prof.last_name}")
            for tag, count in prof.tags[:6]:
                lines.append(f"- {tag} ({count}x)")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phase 2: Intelligence tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def predict_grade(
    university: str,
    course: str,
    professor: str,
    student_gpa: float,
) -> str:
    """Predict likely grade outcome for a student based on historical data.

    Uses the professor's grade distribution for this course combined with
    the student's GPA to estimate grade probabilities. Higher GPA relative
    to the course average means higher chance of A/B.

    Args:
        university: University identifier (e.g. 'utd').
        course: Course code (e.g. 'CS 3341').
        professor: Professor last name.
        student_gpa: Student's current GPA (0.0 to 4.0).
    """
    student_gpa = max(0.0, min(4.0, student_gpa))
    prefix, number = _parse_course(course)

    try:
        dists = await _grades.get_distribution(university, prefix, number, professor)
    except (RMPError, GradesError) as e:
        return f"Error: {e}"

    if not dists:
        return f"No grade data for {prefix} {number} with professor {professor}"

    # Aggregate across semesters
    total = sum(d.total_graded for d in dists)
    if total == 0:
        return "Insufficient data for prediction."

    a_total = sum(d.a_plus + d.a + d.a_minus for d in dists)
    b_total = sum(d.b_plus + d.b + d.b_minus for d in dists)
    c_total = sum(d.c_plus + d.c + d.c_minus for d in dists)
    d_total = sum(d.d_plus + d.d + d.d_minus for d in dists)
    f_total = sum(d.f for d in dists)

    # Base probabilities from distribution
    base = {
        "A": a_total / total,
        "B": b_total / total,
        "C": c_total / total,
        "D": d_total / total,
        "F": f_total / total,
    }

    # Course average GPA
    valid = [d for d in dists if d.avg_gpa is not None]
    course_gpa = sum(d.avg_gpa * d.total_graded for d in valid) / total if valid else 2.5

    # Adjust based on student GPA relative to course average
    # Students above average get probability shifted upward
    gap = student_gpa - course_gpa
    shift = gap * 0.15  # 15% shift per GPA point difference

    adjusted = {}
    grades_ordered = ["A", "B", "C", "D", "F"]
    for i, g in enumerate(grades_ordered):
        boost = shift * (2 - i)  # A gets most boost, F gets most penalty
        adjusted[g] = max(0.01, base[g] + boost)
    # Normalize
    total_adj = sum(adjusted.values())
    for g in adjusted:
        adjusted[g] = round(adjusted[g] / total_adj * 100, 1)

    most_likely = max(adjusted, key=adjusted.get)  # type: ignore[arg-type]

    lines = [
        f"# Grade Prediction: {prefix} {number}",
        f"Professor: {professor} | Your GPA: {student_gpa}",
        "",
        f"Course average GPA: {course_gpa:.2f} ({total} students across {len(dists)} semesters)",
    ]

    if student_gpa > course_gpa + 0.5:
        lines.append(f"Your GPA is well above the course average -- strong position.")
    elif student_gpa > course_gpa:
        lines.append(f"Your GPA is above the course average -- good position.")
    elif student_gpa > course_gpa - 0.5:
        lines.append(f"Your GPA is near the course average -- typical outcome expected.")
    else:
        lines.append(f"Your GPA is below the course average -- challenging but achievable.")

    lines.extend([
        "",
        "## Predicted Grade Probabilities",
        "",
        "| Grade | Probability |",
        "|-------|-------------|",
    ])
    for g in grades_ordered:
        marker = " <--" if g == most_likely else ""
        lines.append(f"| {g} | {adjusted[g]}%{marker} |")

    lines.extend([
        "",
        f"**Most likely outcome: {most_likely}** ({adjusted[most_likely]}%)",
        "",
        f"Based on {total} historical student outcomes.",
    ])

    return "\n".join(lines)


@mcp.tool()
async def recommend_professor(
    university: str,
    course: str,
    professors: list[str],
    learning_style: str | None = None,
    priorities: list[str] | None = None,
) -> str:
    """Rank professors for a course based on teaching style and student priorities.

    Scores each professor on grade outcomes, teaching quality, and how well
    they match the student's learning style and priorities. Returns a ranked
    recommendation with explanations.

    Note: requires professor names because course catalog scraping is not yet
    available. Use search_professors to find candidates first.

    Args:
        university: University identifier (e.g. 'utd').
        course: Course code (e.g. 'CS 3341').
        professors: List of professor names to evaluate.
        learning_style: Student's learning style. Supported values:
            'visual', 'hands_on', 'reading', 'lecture', 'self_directed'.
        priorities: Optional list of priorities. Supported values:
            'easy_a' (high GPA), 'clear_lectures', 'low_workload',
            'accessible', 'engaging', 'learn_a_lot'.
    """
    if not professors:
        return "Provide at least one professor name to evaluate."

    priorities = priorities or []
    learning_style = (learning_style or "").lower().strip()
    prefix, number = _parse_course(course)

    async def _evaluate(name: str) -> dict | None:
        try:
            results = await _rmp.search(university, name)
            if not results:
                return None
            prof = await _rmp.profile(results[0].rmp_id)
        except (RMPError, GradesError):
            return None

        # Get grade data
        try:
            dists = await _grades.get_distribution(university, prefix, number, name)
        except (RMPError, GradesError):
            dists = []

        course_gpa = None
        if dists:
            valid = [d for d in dists if d.avg_gpa is not None and d.total_graded > 0]
            if valid:
                course_gpa = round(
                    sum(d.avg_gpa * d.total_graded for d in valid)
                    / sum(d.total_graded for d in valid),
                    2,
                )

        # Scoring
        score = 0.0
        strengths: list[str] = []
        concerns: list[str] = []

        # Base score from rating and WTA
        if prof.avg_rating:
            score += prof.avg_rating * 10  # 0-50
        if prof.would_take_again and prof.would_take_again >= 0:
            score += prof.would_take_again * 0.3  # 0-30

        ts = prof.teaching_style

        # Priority adjustments
        for p in priorities:
            if p == "easy_a" and course_gpa:
                bonus = (course_gpa - 2.5) * 15
                score += bonus
                if course_gpa >= 3.0:
                    strengths.append(f"High course GPA ({course_gpa})")
            elif p == "clear_lectures" and isinstance(ts, TeachingStyle):
                if ts.lecture_quality == "clear":
                    score += 15
                    strengths.append("Clear lectures")
                elif ts.lecture_quality == "unclear":
                    score -= 15
                    concerns.append("Lecture clarity concerns")
            elif p == "low_workload" and isinstance(ts, TeachingStyle):
                if ts.homework_load == "light":
                    score += 12
                    strengths.append("Light workload")
                elif ts.homework_load == "heavy":
                    score -= 12
                    concerns.append("Heavy workload")
            elif p == "accessible" and isinstance(ts, TeachingStyle):
                if ts.accessibility == "high":
                    score += 10
                    strengths.append("Highly accessible")
                elif ts.accessibility == "low":
                    score -= 10
                    concerns.append("Limited accessibility")
            elif p == "engaging":
                if prof.avg_rating and prof.avg_rating >= 4.0:
                    score += 10
                    strengths.append("Highly rated")
            elif p == "learn_a_lot":
                if prof.avg_difficulty and prof.avg_difficulty >= 3.5:
                    score += 8
                    strengths.append("Rigorous course")

        # Learning style matching
        if learning_style and isinstance(ts, TeachingStyle):
            if learning_style == "visual" and ts.lecture_quality == "clear":
                score += 8
                strengths.append("Clear visual presentations")
            elif learning_style == "lecture" and ts.lecture_quality == "clear":
                score += 10
                strengths.append("Strong lecture delivery")
            elif learning_style == "self_directed" and ts.accessibility == "high":
                score += 8
                strengths.append("Accessible for independent work")
            elif learning_style == "hands_on" and ts.homework_load == "heavy":
                score += 5
                strengths.append("Lots of hands-on practice")
            elif learning_style == "reading" and ts.uses_textbook is True:
                score += 8
                strengths.append("Textbook-based learning")

        # Warnings from NLP
        warnings = []
        if isinstance(ts, TeachingStyle) and ts.warnings:
            warnings = ts.warnings[:3]

        return {
            "name": f"{prof.first_name} {prof.last_name}",
            "score": round(score, 1),
            "rating": prof.avg_rating,
            "difficulty": prof.avg_difficulty,
            "wta": prof.would_take_again,
            "course_gpa": course_gpa,
            "strengths": strengths,
            "concerns": concerns,
            "warnings": warnings,
            "best_for": ts.best_for if isinstance(ts, TeachingStyle) else [],
        }

    results = await asyncio.gather(*(_evaluate(n) for n in professors))
    evaluated = [r for r in results if r is not None]

    if not evaluated:
        return "Could not evaluate any of the listed professors."

    evaluated.sort(key=lambda r: r["score"], reverse=True)

    lines = [
        f"# Professor Recommendations: {prefix} {number}",
    ]
    if learning_style:
        lines.append(f"Learning style: {learning_style}")
    if priorities:
        lines.append(f"Priorities: {', '.join(priorities)}")
    lines.append("")

    for rank, r in enumerate(evaluated, 1):
        medal = {1: "[TOP PICK]", 2: "[RUNNER-UP]"}.get(rank, "")
        wta = _fmt_wta(r["wta"])
        lines.extend([
            f"## {rank}. {r['name']} {medal}",
            f"Rating: {r['rating']}/5 | Difficulty: {r['difficulty']}/5 | WTA: {wta}",
        ])
        if r["course_gpa"]:
            lines.append(f"Course GPA for {prefix} {number}: {r['course_gpa']}")
        if r["strengths"]:
            lines.append(f"Strengths: {', '.join(r['strengths'])}")
        if r["concerns"]:
            lines.append(f"Concerns: {', '.join(r['concerns'])}")
        if r["warnings"]:
            lines.append("Warnings:")
            for w in r["warnings"]:
                lines.append(f"  - {w}")
        if r["best_for"]:
            lines.append(f"Best for: {', '.join(r['best_for'])}")
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_prerequisites(
    university: str,
    course: str,
    depth: int = 2,
) -> str:
    """Get prerequisite courses for a given course from the knowledge graph.

    Shows what courses must be completed before taking the target course,
    and what courses the target course unlocks.

    Args:
        university: University identifier (e.g. 'utd').
        course: Course code (e.g. 'CS 3345').
        depth: How many levels deep to show (1=direct only, 2=two levels).
    """
    if university.lower().strip() != "utd":
        return f"Prerequisite data is currently only available for UTD. '{university}' is not supported yet."

    prefix, number = _parse_course(course)
    code = f"{prefix} {number}"
    depth = max(1, min(5, depth))

    tree = _get_prereqs(code, depth)
    unlocks = get_unlocks(code)

    prereqs = tree.get("prerequisites", [])
    if not prereqs and not unlocks:
        return f"No prerequisite data found for {code} at {university.upper()}"

    lines = [f"# Prerequisites: {code}", ""]

    if prereqs:
        lines.append("## Required Before Taking This Course")
        _render_tree(tree, lines, indent=0)
        lines.append("")
    else:
        lines.append("No prerequisites required.")
        lines.append("")

    if unlocks:
        lines.append("## Courses This Unlocks")
        for u in unlocks:
            lines.append(f"- {u}")
        lines.append("")

    return "\n".join(lines)


def _render_tree(node: dict, lines: list[str], indent: int) -> None:
    """Recursively render prerequisite tree."""
    prereqs = node.get("prerequisites", [])
    children = node.get("children", [])

    if indent == 0:
        for p in prereqs:
            lines.append(f"- {p}")
    if children:
        for child in children:
            prefix = "  " * indent + "- "
            child_prereqs = child.get("prerequisites", [])
            if child_prereqs:
                lines.append(f"{prefix}{child['course']} requires: {', '.join(child_prereqs)}")
            _render_tree(child, lines, indent + 1)


# ---------------------------------------------------------------------------
# Phase 4: Community intel tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def submit_intel(
    university: str,
    course: str,
    professor: str,
    semester: str,
    exam_weight: int | None = None,
    homework_weight: int | None = None,
    curve: str | None = None,
    textbook_required: bool | None = None,
    notes: str | None = None,
) -> str:
    """Submit crowdsourced syllabus intel for a course and professor.

    Community-contributed data about exam weights, curve policies, textbook
    requirements, and other course-specific information. This data helps
    other students make informed decisions.

    Args:
        university: University identifier (e.g. 'utd').
        course: Course code (e.g. 'CS 3341').
        professor: Professor's name.
        semester: Semester code (e.g. '26S' for Spring 2026).
        exam_weight: Percentage of grade from exams (0-100).
        homework_weight: Percentage of grade from homework (0-100).
        curve: Curve policy ('none', 'unlikely', 'likely', 'guaranteed').
        textbook_required: Whether the textbook is required.
        notes: Free-text notes about the course (max 500 chars).
    """
    if exam_weight is not None and not (0 <= exam_weight <= 100):
        return "Error: exam_weight must be between 0 and 100."
    if homework_weight is not None and not (0 <= homework_weight <= 100):
        return "Error: homework_weight must be between 0 and 100."
    if curve and curve not in ("none", "unlikely", "likely", "guaranteed"):
        return "Error: curve must be 'none', 'unlikely', 'likely', or 'guaranteed'."

    prefix, number = _parse_course(course)
    entry = IntelEntry(
        university=university,
        course=f"{prefix} {number}",
        professor=professor,
        semester=semester.upper(),
        exam_weight=exam_weight,
        homework_weight=homework_weight,
        curve=curve,
        textbook_required=textbook_required,
        notes=(notes or "")[:500] if notes else None,
    )

    entry_id = _intel.submit(entry)
    return (
        f"Intel submitted (ID: {entry_id}). "
        f"Course: {prefix} {number}, Professor: {professor}, Semester: {semester}. "
        "Thank you for contributing!"
    )


@mcp.tool()
async def get_intel(
    university: str,
    course: str,
    professor: str | None = None,
) -> str:
    """Get community-contributed syllabus intel for a course.

    Returns crowdsourced data about exam weights, curve policies, textbook
    requirements, and student notes. Data is contributed by other students
    via submit_intel.

    Args:
        university: University identifier (e.g. 'utd').
        course: Course code (e.g. 'CS 3341').
        professor: Optional professor name to filter results.
    """
    prefix, number = _parse_course(course)
    entries = _intel.query(university, f"{prefix} {number}", professor)

    if not entries:
        extra = f" with {professor}" if professor else ""
        return (
            f"No community intel found for {prefix} {number}{extra} at {university.upper()}. "
            "Use submit_intel to contribute!"
        )

    lines = [f"# Community Intel: {prefix} {number}", ""]

    for e in entries:
        lines.append(f"## {e.professor} ({e.semester})")
        if e.exam_weight is not None:
            lines.append(f"- Exam weight: {e.exam_weight}%")
        if e.homework_weight is not None:
            lines.append(f"- Homework weight: {e.homework_weight}%")
        if e.curve:
            lines.append(f"- Curve: {e.curve}")
        if e.textbook_required is not None:
            lines.append(f"- Textbook required: {'yes' if e.textbook_required else 'no'}")
        if e.notes:
            lines.append(f"- Notes: {e.notes}")
        lines.append("")

    total = _intel.count(university)
    lines.append(f"_{total} total intel entries for {university.upper()}_")

    return "\n".join(lines)


def main():
    transport = os.environ.get("PROFGRAPH_TRANSPORT", "stdio")
    if transport == "streamable-http":
        # Extend MCP's Starlette app with REST API routes
        import uvicorn
        from .api import routes as api_routes

        mcp_app = mcp.streamable_http_app()
        # Add REST routes to the MCP app so lifespan is shared
        for route in api_routes:
            mcp_app.routes.append(route)

        port = int(os.environ.get("PROFGRAPH_PORT", "8000"))
        host = os.environ.get("PROFGRAPH_HOST", "0.0.0.0")
        uvicorn.run(mcp_app, host=host, port=port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
