"""Unit tests for community intel storage."""

import tempfile
from pathlib import Path

from profgraph.intel import IntelStore, IntelEntry


def _store() -> IntelStore:
    """Create a temp store for testing."""
    tmp = tempfile.mktemp(suffix=".db")
    return IntelStore(db_path=tmp)


class TestIntelStore:
    def test_submit_and_query(self):
        store = _store()
        entry = IntelEntry(
            university="utd", course="CS 3341", professor="Jason Smith",
            semester="26S", exam_weight=85, homework_weight=15,
            curve="likely", notes="HW is group work",
        )
        entry_id = store.submit(entry)
        assert entry_id > 0

        results = store.query("utd", "CS 3341")
        assert len(results) == 1
        assert results[0].exam_weight == 85
        assert results[0].professor == "Jason Smith"

    def test_query_by_professor(self):
        store = _store()
        store.submit(IntelEntry(
            university="utd", course="CS 3341",
            professor="Jason Smith", semester="26S",
        ))
        store.submit(IntelEntry(
            university="utd", course="CS 3341",
            professor="Beiyu Lin", semester="26S",
        ))
        results = store.query("utd", "CS 3341", professor="Smith")
        assert len(results) == 1
        assert results[0].professor == "Jason Smith"

    def test_query_empty(self):
        store = _store()
        results = store.query("utd", "CS 9999")
        assert results == []

    def test_count(self):
        store = _store()
        assert store.count() == 0
        store.submit(IntelEntry(
            university="utd", course="CS 3341",
            professor="X", semester="26S",
        ))
        store.submit(IntelEntry(
            university="tamu", course="CSCE 121",
            professor="Y", semester="26S",
        ))
        assert store.count() == 2
        assert store.count("utd") == 1
        assert store.count("tamu") == 1

    def test_textbook_bool(self):
        store = _store()
        store.submit(IntelEntry(
            university="utd", course="CS 3341",
            professor="X", semester="26S",
            textbook_required=True,
        ))
        store.submit(IntelEntry(
            university="utd", course="CS 3341",
            professor="Y", semester="26S",
            textbook_required=False,
        ))
        results = store.query("utd", "CS 3341")
        by_prof = {r.professor: r for r in results}
        assert by_prof["X"].textbook_required is True
        assert by_prof["Y"].textbook_required is False

    def test_case_insensitive(self):
        store = _store()
        store.submit(IntelEntry(
            university="UTD", course="cs 3341",
            professor="X", semester="26S",
        ))
        results = store.query("utd", "CS 3341")
        assert len(results) == 1
