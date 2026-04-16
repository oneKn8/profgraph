"""Unit tests for ProfGraph data models (no network required)."""

from profgraph.models import GradeDistribution, ProfessorSummary, ProfessorProfile


class TestGradeDistribution:
    def test_total_graded_excludes_withdrawals(self):
        d = GradeDistribution(semester="23F", a=10, b=5, f=2, w=3)
        assert d.total_graded == 17
        assert d.total == 20

    def test_avg_gpa_basic(self):
        d = GradeDistribution(semester="23F", a=10)
        assert d.avg_gpa == 4.0

    def test_avg_gpa_mixed(self):
        d = GradeDistribution(semester="23F", a=1, f=1)
        assert d.avg_gpa == 2.0

    def test_avg_gpa_none_when_empty(self):
        d = GradeDistribution(semester="23F")
        assert d.avg_gpa is None

    def test_pct_basic(self):
        d = GradeDistribution(semester="23F", a=50, b=30, c=20)
        assert d.pct("A") == 50.0
        assert d.pct("B") == 30.0
        assert d.pct("C") == 20.0

    def test_pct_with_withdrawals(self):
        d = GradeDistribution(semester="23F", a=9, w=1)
        assert d.pct("A") == 90.0
        assert d.pct("W") == 10.0

    def test_pct_zero_total(self):
        d = GradeDistribution(semester="23F")
        assert d.pct("A") == 0.0

    def test_semester_display_fall(self):
        d = GradeDistribution(semester="23F")
        assert d.semester_display == "Fall 2023"

    def test_semester_display_spring(self):
        d = GradeDistribution(semester="24S")
        assert d.semester_display == "Spring 2024"

    def test_semester_display_summer(self):
        d = GradeDistribution(semester="21U")
        assert d.semester_display == "Summer 2021"

    def test_semester_display_unknown_format(self):
        d = GradeDistribution(semester="unknown")
        assert d.semester_display == "unknown"

    def test_semester_display_short(self):
        d = GradeDistribution(semester="XY")
        assert d.semester_display == "XY"

    def test_all_grade_fields(self):
        d = GradeDistribution(
            semester="25F",
            a_plus=10, a=20, a_minus=5,
            b_plus=8, b=15, b_minus=3,
            c_plus=4, c=10, c_minus=2,
            d_plus=1, d=3, d_minus=1,
            f=5, w=3,
        )
        assert d.total_graded == 87
        assert d.total == 90
        assert d.pct("A") == 38.9  # (35/90)*100


class TestProfessorSummary:
    def test_defaults(self):
        p = ProfessorSummary(
            rmp_id="abc", first_name="Jane", last_name="Doe",
            department="CS",
        )
        assert p.avg_rating is None
        assert p.num_ratings == 0


class TestProfessorProfile:
    def test_defaults(self):
        p = ProfessorProfile(
            rmp_id="abc", first_name="Jane", last_name="Doe",
            department="CS",
        )
        assert p.tags == []
        assert p.courses == []
        assert p.reviews == []
