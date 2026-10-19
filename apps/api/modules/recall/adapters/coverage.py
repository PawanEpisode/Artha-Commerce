"""
Coverage adapter (F-02). The only recall file that imports `modules.coverage`: its selectors for the exam date of the
active enrolment (else the term start, one rule for every module that counts down), what the student has started and which
chapters are due for revision, and its public `record_event` service for the one write recall makes (a chapter pass counts as a
revision, FR-F15-64).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from uuid import UUID

from django.db import transaction

from modules.coverage import selectors as coverage
from modules.coverage import services as coverage_services

from ..domain.scheduling import study_day_start


def exam_date(user_id):
    """The student's exam date (a `date`), or None: her own date on the active enrolment, else the start of her target term."""
    enrollment = coverage.get_active_enrollment(user_id)
    return coverage.exam_date_of(enrollment) if enrollment is not None else None


def course_summary(user_id):
    """The student's active course summary or None."""
    return coverage.course_summary(user_id)


def exam_at(user_id, tz: str, day_start_hour: int) -> datetime | None:
    """The exam as an instant: the first moment of its study day in the student's zone."""
    day = exam_date(user_id)
    return None if day is None else study_day_start(day, tz, day_start_hour)


def started_chapter_ids(user_id, chapter_ids) -> set[UUID]:
    """Of these chapters, the ones the student has started (coverage status other than `not_started`)."""
    ids = [c for c in set(chapter_ids) if c is not None]
    if not ids:
        return set()
    return coverage.started_chapter_ids(user_id, ids)


def active_scheme_id(user_id) -> UUID | None:
    """The scheme of her active enrolment: the cards of "my chapters" are the ones linked to it."""
    enrollment = coverage.get_active_enrollment(user_id)
    return enrollment.scheme_id if enrollment is not None else None


def exam_audience(first: date, last: date, after=None, limit: int = 200) -> list:
    """Students with an exam date from `first` to `last`, in id order, one page at a time (for the nightly horizon job)."""
    return coverage.exam_audience(first=first, last=last, after=after, limit=limit)


def due_revision_chapter_ids(user_id, today: date) -> set[UUID]:
    """Chapters of her active enrolment whose revision date has arrived (F-02 "due for revision"); empty without an enrolment."""
    enrollment = coverage.get_active_enrollment(user_id)
    if enrollment is None:
        return set()
    return {row.chapter_id for row in coverage.due_for_revision(enrollment, today)}


PASS_NAMESPACE = uuid.UUID("c8f0a4b2-5d1e-4f63-9a77-2b3e6d0c15f4")


def record_revision_done(user_id, chapter_id, *, session_id) -> bool:
    """
    One `revision_done` on the chapter because its recall set was passed (source `system`, so no coverage migration). Idempotent on a
    client id built from the student, chapter and session, so a replayed event or retried job adds nothing. Never raises for a
    student who is not enrolled in the chapter's syllabus (an old scheme, an archived or missing enrolment): it answers False.
    Returns True when a new revision was recorded.
    """
    with transaction.atomic():
        result = coverage_services.record_event_result(
            user_id,
            chapter_id,
            "revision_done",
            None,
            "system",
            uuid.uuid5(PASS_NAMESPACE, f"{user_id}:{chapter_id}:{session_id}"),
            source_ref=str(session_id),
            strict=False,
        )
    return result.created
