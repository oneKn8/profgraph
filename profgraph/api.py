"""REST API layer for ChatGPT Actions and direct HTTP clients.

Wraps ProfGraph's core logic as standard REST endpoints.
Runs alongside the MCP server on the same uvicorn instance.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .cache import TTLCache
from .grades import GradesClient, GradesError
from .intel import IntelStore, IntelEntry
from .nlp import TeachingStyle
from .prerequisites import get_prerequisites as _get_prereqs, get_unlocks
from .rmp import RMPClient, RMPError
from .universities import list_supported, resolve as resolve_university

_cache = TTLCache(default_ttl=86400)
_rmp = RMPClient(_cache)
_grades = GradesClient(_cache)
_intel = IntelStore()


def _parse_course(course: str) -> tuple[str, str]:
    c = course.strip().upper().replace("-", " ").replace("_", " ")
    if " " in c:
        prefix, number = c.split(None, 1)
        return prefix, number.strip()
    i = 0
    while i < len(c) and c[i].isalpha():
        i += 1
    return c[:i], c[i:]


def _err(msg: str, status: int = 400) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=status)


# ---- Endpoints ----

async def universities(request: Request) -> JSONResponse:
    unis = list_supported()
    return JSONResponse({
        "universities": [
            {
                "key": u.key, "name": u.name,
                "city": u.city, "state": u.state,
                "has_grade_data": u.grade_source != "none",
            }
            for u in unis
        ]
    })


async def search(request: Request) -> JSONResponse:
    uni = request.query_params.get("university", "")
    query = request.query_params.get("query", "")
    dept = request.query_params.get("department")
    if not uni or not query:
        return _err("'university' and 'query' params required")

    try:
        results = await _rmp.search(uni, query)
    except (RMPError, ValueError) as e:
        return _err(str(e))

    if dept:
        dl = dept.lower()
        results = [p for p in results if dl in p.department.lower()]

    return JSONResponse({
        "professors": [
            {
                "name": f"{p.first_name} {p.last_name}",
                "department": p.department,
                "rating": p.avg_rating,
                "difficulty": p.avg_difficulty,
                "would_take_again_pct": p.would_take_again,
                "num_reviews": p.num_ratings,
            }
            for p in results
        ]
    })


async def profile(request: Request) -> JSONResponse:
    uni = request.query_params.get("university", "")
    name = request.query_params.get("professor", "")
    if not uni or not name:
        return _err("'university' and 'professor' params required")

    try:
        results = await _rmp.search(uni, name)
        if not results:
            return _err(f"Professor '{name}' not found", 404)
        prof = await _rmp.profile(results[0].rmp_id)
    except (RMPError, ValueError) as e:
        return _err(str(e))

    ts = prof.teaching_style
    style = None
    if isinstance(ts, TeachingStyle):
        style = {
            "exam_style": ts.exam_style,
            "homework_load": ts.homework_load,
            "lecture_quality": ts.lecture_quality,
            "curve_likelihood": ts.curve_likelihood,
            "accessibility": ts.accessibility,
            "uses_textbook": ts.uses_textbook,
            "records_lectures": ts.records_lectures,
            "provides_practice_exams": ts.provides_practice_exams,
            "warnings": ts.warnings,
            "best_for": ts.best_for,
            "worst_for": ts.worst_for,
        }

    return JSONResponse({
        "name": f"{prof.first_name} {prof.last_name}",
        "department": prof.department,
        "rating": prof.avg_rating,
        "difficulty": prof.avg_difficulty,
        "would_take_again_pct": prof.would_take_again,
        "num_reviews": prof.num_ratings,
        "tags": [{"name": n, "count": c} for n, c in prof.tags[:12]],
        "courses": [{"name": n, "count": c} for n, c in prof.courses],
        "teaching_style": style,
        "recent_reviews": prof.reviews[:8],
    })


async def grades(request: Request) -> JSONResponse:
    uni = request.query_params.get("university", "")
    course = request.query_params.get("course", "")
    professor = request.query_params.get("professor")
    semester = request.query_params.get("semester")
    if not uni or not course:
        return _err("'university' and 'course' params required")

    prefix, number = _parse_course(course)
    try:
        dists = await _grades.get_distribution(uni, prefix, number, professor, semester)
    except (GradesError, ValueError) as e:
        return _err(str(e))

    return JSONResponse({
        "course": f"{prefix} {number}",
        "semesters": len(dists),
        "total_students": sum(d.total for d in dists),
        "distributions": [
            {
                "semester": d.semester_display,
                "semester_code": d.semester,
                "total": d.total,
                "avg_gpa": d.avg_gpa,
                "a_pct": d.pct("A"), "b_pct": d.pct("B"),
                "c_pct": d.pct("C"), "d_pct": d.pct("D"),
                "f_pct": d.pct("F"), "w_pct": d.pct("W"),
            }
            for d in dists[:10]
        ],
    })


async def predict(request: Request) -> JSONResponse:
    uni = request.query_params.get("university", "")
    course = request.query_params.get("course", "")
    professor = request.query_params.get("professor", "")
    gpa_str = request.query_params.get("gpa", "")
    if not all([uni, course, professor, gpa_str]):
        return _err("'university', 'course', 'professor', 'gpa' params required")

    try:
        student_gpa = max(0.0, min(4.0, float(gpa_str)))
    except ValueError:
        return _err("'gpa' must be a number between 0.0 and 4.0")

    prefix, number = _parse_course(course)
    try:
        dists = await _grades.get_distribution(uni, prefix, number, professor)
    except (GradesError, ValueError) as e:
        return _err(str(e))

    if not dists:
        return _err(f"No grade data for {prefix} {number} with {professor}", 404)

    total = sum(d.total_graded for d in dists)
    if total == 0:
        return _err("Insufficient data")

    a_t = sum(d.a_plus + d.a + d.a_minus for d in dists)
    b_t = sum(d.b_plus + d.b + d.b_minus for d in dists)
    c_t = sum(d.c_plus + d.c + d.c_minus for d in dists)
    d_t = sum(d.d_plus + d.d + d.d_minus for d in dists)
    f_t = sum(d.f for d in dists)

    base = {"A": a_t/total, "B": b_t/total, "C": c_t/total, "D": d_t/total, "F": f_t/total}

    valid = [d for d in dists if d.avg_gpa is not None]
    course_gpa = sum(d.avg_gpa * d.total_graded for d in valid) / total if valid else 2.5

    gap = student_gpa - course_gpa
    shift = gap * 0.15
    adjusted = {}
    for i, g in enumerate(["A", "B", "C", "D", "F"]):
        adjusted[g] = max(0.01, base[g] + shift * (2 - i))
    total_adj = sum(adjusted.values())
    adjusted = {g: round(v / total_adj * 100, 1) for g, v in adjusted.items()}

    return JSONResponse({
        "course": f"{prefix} {number}",
        "professor": professor,
        "student_gpa": student_gpa,
        "course_avg_gpa": round(course_gpa, 2),
        "total_students": total,
        "probabilities": adjusted,
        "most_likely": max(adjusted, key=adjusted.get),
    })


async def prerequisites(request: Request) -> JSONResponse:
    course = request.query_params.get("course", "")
    depth = int(request.query_params.get("depth", "2"))
    if not course:
        return _err("'course' param required")

    prefix, number = _parse_course(course)
    code = f"{prefix} {number}"
    tree = _get_prereqs(code, max(1, min(5, depth)))
    unlocks_list = get_unlocks(code)

    return JSONResponse({
        "course": code,
        "prerequisites": tree.get("prerequisites", []),
        "unlocks": unlocks_list,
        "tree": tree,
    })


async def openapi_spec(request: Request) -> JSONResponse:
    """Serve the OpenAPI spec for ChatGPT Actions."""
    spec = {
        "openapi": "3.1.0",
        "info": {
            "title": "ProfGraph API",
            "description": "AI Professor Intelligence -- ratings, teaching style, grade distributions, and recommendations for university professors.",
            "version": "0.2.0",
        },
        "servers": [{"url": str(request.base_url).rstrip("/")}],
        "paths": {
            "/api/universities": {
                "get": {
                    "operationId": "listUniversities",
                    "summary": "List supported universities",
                    "responses": {"200": {"description": "List of universities"}},
                }
            },
            "/api/search": {
                "get": {
                    "operationId": "searchProfessors",
                    "summary": "Search for professors by name",
                    "parameters": [
                        {"name": "university", "in": "query", "required": True, "schema": {"type": "string"}, "description": "University key (e.g. 'utd', 'tamu')"},
                        {"name": "query", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Professor name to search"},
                        {"name": "department", "in": "query", "required": False, "schema": {"type": "string"}, "description": "Filter by department"},
                    ],
                    "responses": {"200": {"description": "Matching professors"}},
                }
            },
            "/api/profile": {
                "get": {
                    "operationId": "getProfessorProfile",
                    "summary": "Get detailed professor profile with ratings, NLP teaching style, and reviews",
                    "parameters": [
                        {"name": "university", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "professor", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Professor name"},
                    ],
                    "responses": {"200": {"description": "Professor profile"}},
                }
            },
            "/api/grades": {
                "get": {
                    "operationId": "getGradeDistribution",
                    "summary": "Get historical grade distributions for a course",
                    "parameters": [
                        {"name": "university", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "course", "in": "query", "required": True, "schema": {"type": "string"}, "description": "Course code (e.g. 'CS 3341')"},
                        {"name": "professor", "in": "query", "required": False, "schema": {"type": "string"}},
                        {"name": "semester", "in": "query", "required": False, "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"description": "Grade distributions"}},
                }
            },
            "/api/predict": {
                "get": {
                    "operationId": "predictGrade",
                    "summary": "Predict grade outcome based on student GPA and historical data",
                    "parameters": [
                        {"name": "university", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "course", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "professor", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "gpa", "in": "query", "required": True, "schema": {"type": "number"}, "description": "Student GPA (0.0-4.0)"},
                    ],
                    "responses": {"200": {"description": "Grade prediction"}},
                }
            },
            "/api/prerequisites": {
                "get": {
                    "operationId": "getPrerequisites",
                    "summary": "Get prerequisite courses (UTD CS only)",
                    "parameters": [
                        {"name": "course", "in": "query", "required": True, "schema": {"type": "string"}},
                        {"name": "depth", "in": "query", "required": False, "schema": {"type": "integer", "default": 2}},
                    ],
                    "responses": {"200": {"description": "Prerequisite tree"}},
                }
            },
        },
    }
    return JSONResponse(spec)


routes = [
    Route("/api/openapi.json", openapi_spec),
    Route("/api/universities", universities),
    Route("/api/search", search),
    Route("/api/profile", profile),
    Route("/api/grades", grades),
    Route("/api/predict", predict),
    Route("/api/prerequisites", prerequisites),
]

app = Starlette(routes=routes)
