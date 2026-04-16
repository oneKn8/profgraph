"""ProfGraph MCP Server -- AI Professor Intelligence.

Gives any LLM instant, pre-computed professor intelligence: teaching style,
grade distributions, and student reviews. Connect via MCP to get data-backed
course recommendations instead of hallucinated guesses.
"""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from .cache import TTLCache
from .grades import GradesClient
from .models import ProfessorProfile
from .rmp import RMPClient

mcp = FastMCP("profgraph_mcp")

_cache = TTLCache(default_ttl=86400)
_rmp = RMPClient(_cache)
_grades = GradesClient(_cache)


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
async def search_professors(university: str, query: str) -> str:
    """Search for professors at a university by name.

    Returns matching professors with their overall rating, difficulty score,
    would-take-again percentage, and total review count. Use professor names
    from these results with get_professor_profile for detailed information.

    Args:
        university: University identifier (e.g. 'utd' for UT Dallas).
        query: Professor name or partial name to search for.
    """
    results = await _rmp.search(university, query)
    if not results:
        return f"No professors found matching '{query}' at {university.upper()}"

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

    Args:
        university: University identifier (e.g. 'utd').
        professor: Professor name to look up.
    """
    results = await _rmp.search(university, professor)
    if not results:
        return f"Professor '{professor}' not found at {university.upper()}"

    prof = await _rmp.profile(results[0].rmp_id)

    lines = [
        f"# {prof.first_name} {prof.last_name}",
        f"{prof.department} | {university.upper()}",
        "",
        "## Ratings",
        f"- Overall: {prof.avg_rating}/5",
        f"- Difficulty: {prof.avg_difficulty}/5",
        f"- Would Take Again: {_fmt_wta(prof.would_take_again)}",
        f"- Total Reviews: {prof.num_ratings}",
        "",
    ]

    if prof.tags:
        lines.append("## Teaching Style Tags")
        for name, count in prof.tags[:12]:
            lines.append(f"- {name} ({count}x)")
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
) -> str:
    """Get historical grade distributions for a course from public records.

    Returns letter grade percentages, average GPA, and total enrollment
    broken down by semester. Data comes from FOIA/TPIA public records.
    Optionally filter by professor last name.

    Args:
        university: University identifier (e.g. 'utd').
        course: Course code (e.g. 'CS 3341' or 'CS3341').
        professor: Optional professor last name to filter results.
    """
    prefix, number = _parse_course(course)
    dists = await _grades.get_distribution(prefix, number, professor)

    if not dists:
        extra = f" (professor: {professor})" if professor else ""
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
    if total_graded > 0:
        gpa_sum = sum(
            (d.avg_gpa or 0) * d.total_graded
            for d in dists
            if d.avg_gpa is not None
        )
        overall_gpa = round(gpa_sum / total_graded, 2)

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
    if overall_gpa:
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
        gpa_str = f" | GPA: {d.avg_gpa}" if d.avg_gpa else ""
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

    async def _fetch(name: str) -> tuple[str, ProfessorProfile | None]:
        results = await _rmp.search(university, name)
        if not results:
            return name, None
        return name, await _rmp.profile(results[0].rmp_id)

    fetched = await asyncio.gather(*(_fetch(n) for n in professors))
    profiles: dict[str, ProfessorProfile | None] = dict(fetched)

    if not any(profiles.values()):
        return "None of the specified professors were found."

    names = list(profiles.keys())
    headers = ["Metric"] + [
        f"{p.first_name} {p.last_name}" if p else f"{n} (not found)"
        for n, p in profiles.items()
    ]

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
        cells = [label] + [_cell(profiles[n], attr, fmt) for n in names]
        lines.append("| " + " | ".join(cells) + " |")

    lines.extend(["", "## Top Tags"])

    for name, prof in profiles.items():
        if prof and prof.tags:
            lines.append(f"### {prof.first_name} {prof.last_name}")
            for tag, count in prof.tags[:6]:
                lines.append(f"- {tag} ({count}x)")
            lines.append("")

    return "\n".join(lines)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
