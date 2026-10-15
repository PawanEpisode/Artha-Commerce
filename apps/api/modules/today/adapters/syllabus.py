"""
Syllabus adapter (F-01). The only Today file that imports `modules.syllabus`: the stable keys of chapters, so a task keeps a working
link after a scheme switch, and a check that an id a provider named really exists (a dangling id would break the insert).
"""

from __future__ import annotations

from datetime import date

from modules.syllabus.models import Chapter


def chapter_keys(chapter_ids) -> dict:
    """{chapter_id: chapter key} for the ids that exist."""
    ids = {c for c in chapter_ids if c is not None}
    return dict(Chapter.objects.filter(id__in=ids).values_list("id", "key")) if ids else {}


def next_attempt_start(enrollment, after) -> date | None:
    """The first day of the next open exam term of the student's level that starts after `after` (the planner's "next attempt")."""
    from modules.syllabus.models import ExamTerm

    return (
        ExamTerm.objects.filter(level_id=enrollment.scheme.level_id, is_open=True, exam_start__gt=after)
        .order_by("exam_start")
        .values_list("exam_start", flat=True)
        .first()
    )
