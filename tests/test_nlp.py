"""Unit tests for NLP teaching style extraction."""

from profgraph.nlp import extract_teaching_style, TeachingStyle


def _reviews(comments: list[str], quality: int = 3) -> list[dict]:
    return [{"comment": c, "quality": quality, "difficulty": 3} for c in comments]


class TestExamStyle:
    def test_straightforward(self):
        ts = extract_teaching_style(_reviews([
            "The exams are fair and straightforward, covering exactly what he teaches.",
            "Easy exams if you study the material.",
        ]))
        assert ts.exam_style == "straightforward"

    def test_ambiguous(self):
        ts = extract_teaching_style(_reviews([
            "Exams are nothing like the homework. Very unclear questions.",
            "The exam wording is ambiguous and confusing.",
            "Tricky questions on the exam.",
        ]))
        assert ts.exam_style == "ambiguous"

    def test_mixed_default(self):
        ts = extract_teaching_style(_reviews([
            "The class was okay overall.",
        ]))
        assert ts.exam_style == "mixed"


class TestHomeworkLoad:
    def test_heavy(self):
        ts = extract_teaching_style(_reviews([
            "Lots of homework every week, the workload is overwhelming.",
            "So much work in this class, too much homework.",
        ]))
        assert ts.homework_load == "heavy"

    def test_light(self):
        ts = extract_teaching_style(_reviews([
            "Light workload, not much homework.",
            "Easy homework, barely any assignments.",
        ]))
        assert ts.homework_load == "light"


class TestCurve:
    def test_guaranteed(self):
        ts = extract_teaching_style(_reviews([
            "Always curves the final grade.",
            "Generous curve at the end.",
        ]))
        assert ts.curve_likelihood == "guaranteed"

    def test_none(self):
        ts = extract_teaching_style(_reviews([
            "No curve at all, doesn't curve.",
        ]))
        assert ts.curve_likelihood == "none"


class TestLectures:
    def test_clear(self):
        ts = extract_teaching_style(_reviews([
            "Great lectures, explains everything clearly.",
            "Amazing lectures, very easy to follow.",
        ]))
        assert ts.lecture_quality == "clear"

    def test_unclear(self):
        ts = extract_teaching_style(_reviews([
            "Confusing lectures, can't teach at all.",
            "Disorganized and hard to follow.",
        ]))
        assert ts.lecture_quality == "unclear"


class TestBooleans:
    def test_uses_textbook(self):
        ts = extract_teaching_style(_reviews([
            "Textbook is required, you need to read the book.",
        ]))
        assert ts.uses_textbook is True

    def test_no_textbook(self):
        ts = extract_teaching_style(_reviews([
            "Don't need the textbook at all.",
        ]))
        assert ts.uses_textbook is False

    def test_practice_exams(self):
        ts = extract_teaching_style(_reviews([
            "She provides practice exams and review sessions.",
        ]))
        assert ts.provides_practice_exams is True


class TestWarnings:
    def test_extracts_from_low_rated(self):
        reviews = [
            {"comment": "Exams are nothing like homework.", "quality": 1, "difficulty": 5},
            {"comment": "Great professor!", "quality": 5, "difficulty": 2},
        ]
        ts = extract_teaching_style(reviews)
        assert len(ts.warnings) > 0
        assert any("differ" in w.lower() for w in ts.warnings)

    def test_no_warnings_from_high_rated(self):
        reviews = [
            {"comment": "Exams are nothing like homework.", "quality": 4, "difficulty": 3},
        ]
        ts = extract_teaching_style(reviews)
        assert len(ts.warnings) == 0


class TestStudentTypes:
    def test_best_for(self):
        ts = extract_teaching_style(_reviews([
            "If you study and work hard, you'll do fine.",
            "Easy if you have prior coding experience.",
        ]))
        assert len(ts.best_for) > 0

    def test_worst_for(self):
        ts = extract_teaching_style(_reviews([
            "Not for beginners, avoid if you're new to coding.",
        ]))
        assert len(ts.worst_for) > 0


class TestEdgeCases:
    def test_empty_reviews(self):
        ts = extract_teaching_style([])
        assert ts.exam_style == "unknown"

    def test_no_comments(self):
        ts = extract_teaching_style([{"quality": 3}])
        assert ts.exam_style == "unknown"
