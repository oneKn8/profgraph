"""Live API tests for ProfGraph tools."""

import asyncio
import sys

from profgraph.cache import TTLCache

_cache = TTLCache()


async def test_search():
    from profgraph.rmp import RMPClient

    cache = _cache
    client = RMPClient(cache)
    results = await client.search("utd", "Jason Smith")
    assert len(results) > 0, "No results for Jason Smith"
    jason = results[0]
    assert jason.last_name == "Smith"
    assert jason.avg_rating is not None
    print(f"  search: {jason.first_name} {jason.last_name} - {jason.avg_rating}/5, {jason.num_ratings} reviews")
    return jason.rmp_id


async def test_profile(rmp_id: str):
    from profgraph.rmp import RMPClient
    

    cache = _cache
    client = RMPClient(cache)
    prof = await client.profile(rmp_id)
    assert prof.first_name == "Jason"
    assert len(prof.tags) > 0, "No tags"
    assert len(prof.courses) > 0, "No courses"
    assert len(prof.reviews) > 0, "No reviews"
    print(f"  profile: {len(prof.tags)} tags, {len(prof.courses)} courses, {len(prof.reviews)} reviews")
    print(f"  top tags: {', '.join(t[0] for t in prof.tags[:5])}")


async def test_grades():
    from profgraph.grades import GradesClient
    

    cache = _cache
    client = GradesClient(cache)
    dists = await client.get_distribution("utd", "CS", "3341")
    assert len(dists) > 0, "No grade data"
    latest = dists[0]
    assert latest.total > 0
    assert latest.avg_gpa is not None
    print(f"  grades: {len(dists)} semesters, latest={latest.semester_display} ({latest.total} students, GPA={latest.avg_gpa})")


async def test_grades_filtered():
    from profgraph.grades import GradesClient
    

    cache = _cache
    client = GradesClient(cache)
    dists = await client.get_distribution("utd", "CS", "3341", professor="smith")
    print(f"  grades filtered (smith): {len(dists)} semesters")


async def test_tool_search():
    from profgraph.server import search_professors
    result = await search_professors("utd", "Beiyu Lin")
    assert "Beiyu" in result or "Lin" in result
    print(f"  tool search_professors: {len(result)} chars")


async def test_tool_profile():
    from profgraph.server import get_professor_profile
    result = await get_professor_profile("utd", "Jason Smith")
    assert "Jason" in result
    assert "Tags" in result or "tag" in result.lower()
    print(f"  tool get_professor_profile: {len(result)} chars")


async def test_tool_grades():
    from profgraph.server import get_grade_distribution
    result = await get_grade_distribution("utd", "CS 3341")
    assert "Grade Distribution" in result
    assert "GPA" in result
    print(f"  tool get_grade_distribution: {len(result)} chars")


async def test_tool_compare():
    from profgraph.server import compare_professors
    result = await compare_professors("utd", ["Jason Smith", "Beiyu Lin"])
    assert "Comparison" in result
    print(f"  tool compare_professors: {len(result)} chars")


async def main():
    tests = [
        ("RMP search", test_search),
        ("Grades", test_grades),
        ("Grades filtered", test_grades_filtered),
        ("Tool: search_professors", test_tool_search),
        ("Tool: get_professor_profile", test_tool_profile),
        ("Tool: get_grade_distribution", test_tool_grades),
        ("Tool: compare_professors", test_tool_compare),
    ]

    passed = 0
    failed = 0

    for name, fn in tests:
        try:
            if name == "RMP search":
                rmp_id = await fn()
                # Run profile test with the ID
                print(f"[PASS] {name}")
                passed += 1
                try:
                    print(f"[....] RMP profile")
                    await test_profile(rmp_id)
                    print(f"[PASS] RMP profile")
                    passed += 1
                except Exception as e:
                    print(f"[FAIL] RMP profile: {e}")
                    failed += 1
            else:
                print(f"[....] {name}")
                await fn()
                print(f"[PASS] {name}")
                passed += 1
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
