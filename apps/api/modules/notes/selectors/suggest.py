"""Candidates for chapter suggestions: the chapters of the student's enrolled syllabus, or a level's current scheme."""

from __future__ import annotations

from modules.coverage import selectors as coverage
from modules.syllabus import selectors as syllabus

from ..domain.chapter_suggest import Candidate, Suggestion, suggest

__all__ = ["Suggestion", "suggestions_for"]


def candidates(user_id, level_id=None) -> list[Candidate]:
    if level_id:
        scheme_ids = [s] if (s := syllabus.current_scheme_id(level_id)) else []
    else:
        scheme_ids = [e.scheme_id for e in coverage.list_enrollments(user_id) if e.status == "active"]
    return [
        Candidate(r.id, r.key, r.name, r.subject_id, r.subject_key, r.subject_name)
        for scheme_id in scheme_ids
        for r in syllabus.chapters_for_scheme(scheme_id)
    ]


def suggestions_for(user_id, text: str, level_id=None) -> list[Suggestion]:
    return suggest(text, candidates(user_id, level_id))
