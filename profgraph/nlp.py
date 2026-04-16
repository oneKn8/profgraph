"""Teaching style extraction from RMP review text.

Uses keyword pattern matching to classify professor teaching style
from free-text student reviews. Each classifier scans all reviews,
counts positive/negative signals, and returns a categorical label.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TeachingStyle:
    """Structured teaching style extracted from RMP reviews."""

    exam_style: str = "unknown"         # straightforward | mixed | ambiguous | tricky
    homework_load: str = "unknown"      # light | moderate | heavy
    curve_likelihood: str = "unknown"   # none | low | medium | high | guaranteed
    lecture_quality: str = "unknown"    # clear | mixed | unclear
    accessibility: str = "unknown"      # high | medium | low
    uses_textbook: bool | None = None
    records_lectures: bool | None = None
    provides_practice_exams: bool | None = None
    warnings: list[str] = field(default_factory=list)
    best_for: list[str] = field(default_factory=list)
    worst_for: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pattern definitions: (regex_pattern, weight)
# Positive weight = evidence FOR the label, negative = AGAINST
# ---------------------------------------------------------------------------

_EXAM_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "straightforward": [
        (r"(fair|straightforward|reasonable)\s*(exam|test|midterm|final)", 1.0),
        (r"exam.{0,20}(what (he|she|they) (taught|teaches|covered))", 1.0),
        (r"(easy|simple)\s*(exam|test)", 0.8),
        (r"(open.?note|open.?book)\s*(exam|test|midterm|final)", 0.8),
        (r"(practice exam|review session).{0,15}(help|useful|great)", 0.6),
    ],
    "ambiguous": [
        (r"(unclear|ambiguous|confusing|vague)\s*(exam|test|question|wording)", 1.0),
        (r"exam.{0,25}(nothing like|different from).{0,15}(homework|hw|lecture|class)", 1.2),
        (r"(tricky|trick)\s*(question|exam|test|wording)", 0.9),
        (r"exam.{0,15}(last minute|mistakes|typos|errors)", 0.8),
        (r"(not specific|no guidance).{0,15}(exam|test)", 0.7),
    ],
}

_HOMEWORK_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "heavy": [
        (r"(lots of|so much|too much|excessive|extreme)\s*(homework|hw|work|assignment|project)", 1.0),
        (r"(heavy|overwhelming|insane)\s*(workload|work\s*load|amount of work)", 1.0),
        (r"half.{0,10}(course\s*work|time|semester).{0,15}(his|her|this) class", 0.8),
    ],
    "light": [
        (r"(easy|light|minimal|not much)\s*(homework|hw|workload|work)", 1.0),
        (r"(barely any|no)\s*(homework|hw|assignment)", 0.9),
    ],
}

_CURVE_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "guaranteed": [
        (r"(always|definitely|generous)\s*curve", 1.0),
        (r"curve.{0,10}(saved|helps|generous)", 0.8),
    ],
    "high": [
        (r"(does|will|might)\s*curve", 0.8),
        (r"(there.{0,5}(is|was) a curve|curved the (class|grade|final))", 0.9),
    ],
    "none": [
        (r"(no|doesn.?t|does not|never)\s*curve", 1.0),
        (r"no curve", 1.0),
    ],
}

_LECTURE_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "clear": [
        (r"(clear|great|amazing|excellent|good|helpful)\s*(lecture|explanation|teaching)", 1.0),
        (r"(explains|teaches).{0,15}(well|clearly|great)", 0.9),
        (r"(easy to (follow|understand)|very (clear|organized))", 0.8),
    ],
    "unclear": [
        (r"(confusing|unclear|bad|terrible|horrible)\s*(lecture|explanation|teaching)", 1.0),
        (r"(can.?t|doesn.?t|does not)\s*(teach|explain)", 0.9),
        (r"(hard to (follow|understand)|disorganized|not organized)", 0.8),
        (r"(reads? (off|from) (slides?|notes?))", 0.6),
    ],
}

_ACCESSIBILITY_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "high": [
        (r"(accessible|available|helpful).{0,10}(outside|office|after)\s*(class|hours)", 1.0),
        (r"(office hours|extra help|always (available|willing))", 0.8),
        (r"(responds? (quickly|fast)|easy to (reach|contact|email))", 0.7),
    ],
    "low": [
        (r"(hard to (reach|contact|find)|never (available|responds?))", 1.0),
        (r"(doesn.?t|does not)\s*(respond|answer|reply)", 0.8),
    ],
}

_BOOL_PATTERNS: dict[str, list[tuple[str, float]]] = {
    "uses_textbook_yes": [
        (r"(textbook|book)\s*(required|mandatory|necessary|needed|helpful)", 1.0),
        (r"(follow|read|use).{0,10}(textbook|book)", 0.7),
    ],
    "uses_textbook_no": [
        (r"(no|don.?t need|doesn.?t use|never use)\s*(the\s+)?(textbook|book)", 1.0),
    ],
    "records_lectures_yes": [
        (r"(records?|posts?|uploads?)\s*(lecture|class|video)", 1.0),
    ],
    "records_lectures_no": [
        (r"(doesn.?t|does not)\s*(record|post|upload)\s*(lecture|class)", 1.0),
        (r"no.{0,5}(recorded|recording)", 0.8),
    ],
    "practice_exams_yes": [
        (r"(practice|sample|old)\s*(exam|test|midterm|final)", 1.0),
        (r"(review session|study guide|exam review)", 0.8),
    ],
    "practice_exams_no": [
        (r"(no|doesn.?t|never).{0,10}(practice|review|study guide)", 1.0),
    ],
}

# Warning patterns: extracted from low-rated reviews
_WARNING_PATTERNS: list[tuple[str, str]] = [
    (r"exam.{0,25}(nothing like|different from).{0,15}(homework|hw|lecture)", "Exams differ significantly from homework/lectures"),
    (r"(doesn.?t|does not)\s*(teach|explain).{0,15}(well|clearly)", "Lectures may lack clarity"),
    (r"(attendance|mandatory|required).{0,10}(but|yet).{0,15}(useless|waste|pointless)", "Mandatory attendance with limited lecture value"),
    (r"(grading|grade).{0,10}(harsh|unfair|inconsistent|arbitrary)", "Grading perceived as harsh or inconsistent"),
    (r"(last minute|disorganized|unorganized|unprepared)", "Course organization issues reported"),
    (r"(no (curve|extra credit|review|practice))", "No safety nets (curve/extra credit/review)"),
]

# Student-type patterns
_BEST_FOR_PATTERNS: list[tuple[str, str]] = [
    (r"(if you (study|work hard|put in (the )?effort|stay on top))", "self-motivated studiers"),
    (r"(self.?taught|teach yourself|learn on your own)", "independent learners"),
    (r"(prior (experience|knowledge|coding)|already know)", "students with prior experience"),
    (r"(easy|simple|great).{0,10}(if you (attend|go to) (class|lecture))", "consistent class attenders"),
]

_WORST_FOR_PATTERNS: list[tuple[str, str]] = [
    (r"(not (for|good for)|avoid if).{0,15}(beginner|new to|first time)", "beginners without prior experience"),
    (r"(visual learner|need (visual|hands.on))", "visual or hands-on learners"),
    (r"(need (structure|guidance|help|clear instruction))", "students needing structured guidance"),
    (r"(procrastinat|last minute|cram)", "procrastinators"),
]


def _score_patterns(
    texts: list[str], patterns: dict[str, list[tuple[str, float]]]
) -> dict[str, float]:
    """Score each label by scanning all texts against its patterns."""
    scores: dict[str, float] = {label: 0.0 for label in patterns}
    for text in texts:
        lower = text.lower()
        for label, pats in patterns.items():
            for regex, weight in pats:
                if re.search(regex, lower):
                    scores[label] += weight
    return scores


def _classify(scores: dict[str, float], default: str = "mixed") -> str:
    """Pick the highest-scoring label, or default if no signal."""
    best = max(scores, key=scores.get)  # type: ignore[arg-type]
    if scores[best] < 0.5:
        return default
    return best


def _detect_bool(
    texts: list[str], yes_key: str, no_key: str
) -> bool | None:
    """Detect boolean from review text. Returns None if insufficient signal."""
    yes_score = 0.0
    no_score = 0.0
    for text in texts:
        lower = text.lower()
        for regex, weight in _BOOL_PATTERNS.get(yes_key, []):
            if re.search(regex, lower):
                yes_score += weight
        for regex, weight in _BOOL_PATTERNS.get(no_key, []):
            if re.search(regex, lower):
                no_score += weight
    if yes_score < 0.5 and no_score < 0.5:
        return None
    return yes_score > no_score


def _extract_list(
    texts: list[str], patterns: list[tuple[str, str]]
) -> list[str]:
    """Extract matching labels from review text, deduplicated."""
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        lower = text.lower()
        for regex, label in patterns:
            if label not in seen and re.search(regex, lower):
                found.append(label)
                seen.add(label)
    return found


def _extract_warnings(reviews: list[dict]) -> list[str]:
    """Extract warnings from low-rated reviews (quality <= 2)."""
    low_rated = [r.get("comment", "") for r in reviews if (r.get("quality") or 5) <= 2]
    return _extract_list(low_rated, _WARNING_PATTERNS)


def extract_teaching_style(reviews: list[dict]) -> TeachingStyle:
    """Extract structured teaching style from a list of RMP reviews.

    Args:
        reviews: List of review dicts with 'comment', 'quality', 'difficulty' fields.

    Returns:
        TeachingStyle with classified fields.
    """
    if not reviews:
        return TeachingStyle()

    texts = [r.get("comment", "") for r in reviews if r.get("comment")]
    if not texts:
        return TeachingStyle()

    return TeachingStyle(
        exam_style=_classify(_score_patterns(texts, _EXAM_PATTERNS), "mixed"),
        homework_load=_classify(_score_patterns(texts, _HOMEWORK_PATTERNS), "moderate"),
        curve_likelihood=_classify(_score_patterns(texts, _CURVE_PATTERNS), "unknown"),
        lecture_quality=_classify(_score_patterns(texts, _LECTURE_PATTERNS), "mixed"),
        accessibility=_classify(_score_patterns(texts, _ACCESSIBILITY_PATTERNS), "unknown"),
        uses_textbook=_detect_bool(texts, "uses_textbook_yes", "uses_textbook_no"),
        records_lectures=_detect_bool(texts, "records_lectures_yes", "records_lectures_no"),
        provides_practice_exams=_detect_bool(texts, "practice_exams_yes", "practice_exams_no"),
        warnings=_extract_warnings(reviews),
        best_for=_extract_list(texts, _BEST_FOR_PATTERNS),
        worst_for=_extract_list(texts, _WORST_FOR_PATTERNS),
    )
