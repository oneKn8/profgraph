"""Unit tests for prerequisite knowledge graph."""

from profgraph.prerequisites import get_prerequisites, get_unlocks, get_all_courses


class TestGetPrerequisites:
    def test_cs3345_has_prereqs(self):
        result = get_prerequisites("CS 3345")
        assert result["course"] == "CS 3345"
        assert "CS 2305" in result["prerequisites"] or "CS 2336" in result["prerequisites"]

    def test_cs1336_no_prereqs(self):
        result = get_prerequisites("CS 1336")
        assert result["prerequisites"] == []

    def test_depth_2(self):
        result = get_prerequisites("CS 3345", depth=2)
        children = result.get("children", [])
        # CS 3345 prereqs have their own prereqs
        if children:
            assert any("prerequisites" in c for c in children)

    def test_unknown_course(self):
        result = get_prerequisites("CS 9999")
        assert result["prerequisites"] == []


class TestGetUnlocks:
    def test_cs1337_unlocks(self):
        unlocks = get_unlocks("CS 1337")
        assert "CS 2305" in unlocks
        assert "CS 2336" in unlocks

    def test_leaf_course(self):
        unlocks = get_unlocks("CS 4347")
        assert unlocks == []


class TestGetAllCourses:
    def test_returns_sorted(self):
        courses = get_all_courses()
        assert len(courses) > 10
        assert courses == sorted(courses)

    def test_contains_known_courses(self):
        courses = get_all_courses()
        assert "CS 1337" in courses
        assert "CS 4349" in courses
