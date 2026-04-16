"""Community-contributed syllabus intel storage.

SQLite-backed storage for crowdsourced course data: exam weights,
curve policies, textbook requirements, and professor-specific notes.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = Path(__file__).parent.parent / "data" / "intel.db"


@dataclass
class IntelEntry:
    """A single piece of community-contributed course intel."""

    university: str
    course: str
    professor: str
    semester: str
    exam_weight: int | None = None
    homework_weight: int | None = None
    curve: str | None = None  # none | unlikely | likely | guaranteed
    textbook_required: bool | None = None
    notes: str | None = None
    submitted_at: float = 0.0


class IntelStore:
    """SQLite-backed community intel storage."""

    def __init__(self, db_path: str | Path | None = None):
        self._path = str(db_path or DEFAULT_DB)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    university TEXT NOT NULL,
                    course TEXT NOT NULL,
                    professor TEXT NOT NULL,
                    semester TEXT NOT NULL,
                    exam_weight INTEGER,
                    homework_weight INTEGER,
                    curve TEXT,
                    textbook_required INTEGER,
                    notes TEXT,
                    submitted_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_intel_lookup
                ON intel (university, course, professor)
            """)

    def submit(self, entry: IntelEntry) -> int:
        """Store a new intel entry. Returns the entry ID."""
        entry.submitted_at = entry.submitted_at or time.time()
        with sqlite3.connect(self._path) as conn:
            cursor = conn.execute(
                """INSERT INTO intel
                   (university, course, professor, semester,
                    exam_weight, homework_weight, curve,
                    textbook_required, notes, submitted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.university.lower(),
                    entry.course.upper(),
                    entry.professor,
                    entry.semester,
                    entry.exam_weight,
                    entry.homework_weight,
                    entry.curve,
                    1 if entry.textbook_required else (0 if entry.textbook_required is False else None),
                    entry.notes,
                    entry.submitted_at,
                ),
            )
            return cursor.lastrowid or 0

    def query(
        self,
        university: str,
        course: str,
        professor: str | None = None,
    ) -> list[IntelEntry]:
        """Query intel for a course, optionally filtered by professor."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            if professor:
                rows = conn.execute(
                    """SELECT * FROM intel
                       WHERE university = ? AND course = ? AND professor LIKE ?
                       ORDER BY submitted_at DESC LIMIT 20""",
                    (university.lower(), course.upper(), f"%{professor}%"),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM intel
                       WHERE university = ? AND course = ?
                       ORDER BY submitted_at DESC LIMIT 20""",
                    (university.lower(), course.upper()),
                ).fetchall()

        return [
            IntelEntry(
                university=r["university"],
                course=r["course"],
                professor=r["professor"],
                semester=r["semester"],
                exam_weight=r["exam_weight"],
                homework_weight=r["homework_weight"],
                curve=r["curve"],
                textbook_required=bool(r["textbook_required"]) if r["textbook_required"] is not None else None,
                notes=r["notes"],
                submitted_at=r["submitted_at"],
            )
            for r in rows
        ]

    def count(self, university: str | None = None) -> int:
        """Count total intel entries, optionally filtered by university."""
        with sqlite3.connect(self._path) as conn:
            if university:
                row = conn.execute(
                    "SELECT COUNT(*) FROM intel WHERE university = ?",
                    (university.lower(),),
                ).fetchone()
            else:
                row = conn.execute("SELECT COUNT(*) FROM intel").fetchone()
            return row[0] if row else 0
