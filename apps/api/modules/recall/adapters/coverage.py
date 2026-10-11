"""
Coverage adapter (F-02). The only recall file that imports `modules.coverage`, and only its selectors: the exam date of the
active enrolment (else the term start, one rule for every module that counts down), and what the student has started.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from modules.coverage import selectors as coverage

from ..domain.scheduling import study_day_start


def exam_date(user_id):
    """The student's exam date (a `date`), or None: her own date on the active enrolment, else the start of her target term."""
    enrollment = coverage.get_active_enrollment(user_id)
    return coverage.exam_date_of(enrollment) if enrollment is not None else None


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
