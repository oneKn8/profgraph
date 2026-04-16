"""Data models for ProfGraph professor intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProfessorSummary:
    """Brief professor info from search results."""

    rmp_id: str
    first_name: str
    last_name: str
    department: str
    avg_rating: float | None = None
    avg_difficulty: float | None = None
    would_take_again: float | None = None
    num_ratings: int = 0


@dataclass
class ProfessorProfile:
    """Full professor profile with ratings, tags, courses, and reviews."""

    rmp_id: str
    first_name: str
    last_name: str
    department: str
    avg_rating: float | None = None
    avg_difficulty: float | None = None
    would_take_again: float | None = None
    num_ratings: int = 0
    tags: list[tuple[str, int]] = field(default_factory=list)
    courses: list[tuple[str, int]] = field(default_factory=list)
    reviews: list[dict] = field(default_factory=list)


@dataclass
class GradeDistribution:
    """Grade distribution for a course in a specific semester.

    Nebula API returns a 14-element array:
    [A+, A, A-, B+, B, B-, C+, C, C-, D+, D, D-, F, W]
    """

    semester: str
    a_plus: int = 0
    a: int = 0
    a_minus: int = 0
    b_plus: int = 0
    b: int = 0
    b_minus: int = 0
    c_plus: int = 0
    c: int = 0
    c_minus: int = 0
    d_plus: int = 0
    d: int = 0
    d_minus: int = 0
    f: int = 0
    w: int = 0

    @property
    def total_graded(self) -> int:
        return (
            self.a_plus + self.a + self.a_minus
            + self.b_plus + self.b + self.b_minus
            + self.c_plus + self.c + self.c_minus
            + self.d_plus + self.d + self.d_minus
            + self.f
        )

    @property
    def total(self) -> int:
        return self.total_graded + self.w

    @property
    def avg_gpa(self) -> float | None:
        if self.total_graded == 0:
            return None
        gpa_points = {
            "a_plus": 4.0, "a": 4.0, "a_minus": 3.67,
            "b_plus": 3.33, "b": 3.0, "b_minus": 2.67,
            "c_plus": 2.33, "c": 2.0, "c_minus": 1.67,
            "d_plus": 1.33, "d": 1.0, "d_minus": 0.67,
            "f": 0.0,
        }
        total = sum(gpa_points[k] * getattr(self, k) for k in gpa_points)
        return round(total / self.total_graded, 2)

    def pct(self, letter: str) -> float:
        """Percentage for a letter grade group (A/B/C/D/F/W)."""
        if self.total == 0:
            return 0.0
        counts = {
            "A": self.a_plus + self.a + self.a_minus,
            "B": self.b_plus + self.b + self.b_minus,
            "C": self.c_plus + self.c + self.c_minus,
            "D": self.d_plus + self.d + self.d_minus,
            "F": self.f,
            "W": self.w,
        }
        return round(counts.get(letter, 0) / self.total * 100, 1)

    @property
    def semester_display(self) -> str:
        """Convert '23F' -> 'Fall 2023', '21S' -> 'Spring 2021'.

        Nebula API _id format: 2-digit year + term letter (F/S/U).
        """
        s = self.semester
        if len(s) < 3 or not s[:2].isdigit() or s[2] not in "FSU":
            return s
        names = {"F": "Fall", "S": "Spring", "U": "Summer"}
        return f"{names[s[2]]} 20{s[:2]}"
