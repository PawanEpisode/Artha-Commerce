"""
Coverage adapter (F-03). The only Today file that imports `modules.coverage` for reads: the active enrolment, the exam date (one
rule for every module that counts down), the planned daily minutes and the study state as plain data.
"""

from __future__ import annotations

from datetime import date

from modules.coverage import selectors as coverage

StudyState = coverage.StudyState


def active_enrollment(user_id):
    return coverage.get_active_enrollment(user_id)


def exam_date(enrollment) -> date | None:
    return coverage.exam_date_of(enrollment)


def daily_minutes(enrollment) -> int | None:
    return enrollment.planned_minutes


def study_state(user_id, enrollment, tz: str) -> StudyState:
    return coverage.study_state(user_id, enrollment, tz)


def set_exam_date(enrollment, exam_date: date):
    """The student chose to sit a later attempt: the exam date lives in F-03, so the change goes through its service."""
    from modules.coverage import services as coverage_services

    return coverage_services.update_enrollment(enrollment, data={"exam_date": exam_date})
