"""Reads for the motivation library, what a student was shown, and whether they opened the app today (W3.3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from django.db.models import Q

from modules.coverage import selectors as coverage_selectors
from modules.profiles import selectors as profile_selectors

from ..domain import motivation
from ..domain.enums import MessageStatus, ShownChannel
from ..models import Message, MessageShown

DEFAULT_LOCALE = "en"


@dataclass(frozen=True)
class StudentContext:
    """What narrows a student's pool: their active course and level, and how far away their exam is."""

    course_id: object | None
    level_id: object | None
    days_left: int | None

    @property
    def phase(self):
        return motivation.phase_for(self.days_left)


def student_context(user_id, today: date) -> StudentContext:
    """From the student's active enrolment (read through `coverage`); a student with none gets only general lines."""
    enrollment = coverage_selectors.get_active_enrollment(user_id)
    if enrollment is None:
        return StudentContext(None, None, None)
    exam_date = coverage_selectors.exam_date_of(enrollment)
    days_left = (exam_date - today).days if exam_date else None
    return StudentContext(enrollment.level.course_id, enrollment.level_id, days_left)


def shown_on(user_id, local_date: date) -> MessageShown | None:
    """The message the student already has for this local day, if any (the card and the push share it)."""
    return MessageShown.objects.select_related("message").filter(user_id=user_id, shown_on=local_date).first()


def recently_shown_ids(user_id, today: date) -> set:
    """Messages the student saw inside the no-repeat window ending today (served by the unique index on the day)."""
    return set(
        MessageShown.objects.filter(user_id=user_id, shown_on__gte=motivation.recent_since(today)).values_list(
            "message_id", flat=True
        )
    )


def candidates(context: StudentContext, *, locale: str = DEFAULT_LOCALE) -> list[motivation.Candidate]:
    """Published lines that may go to this student: general ones plus those for their course and level."""
    rows = Message.objects.filter(status=MessageStatus.PUBLISHED, locale=locale)
    rows = rows.filter(
        Q(course__isnull=True) | Q(course_id=context.course_id) if context.course_id else Q(course__isnull=True)
    )
    rows = rows.filter(
        Q(level__isnull=True) | Q(level_id=context.level_id) if context.level_id else Q(level__isnull=True)
    )
    return [
        motivation.Candidate(id=pk, tone=tone, phase=phase)
        for pk, tone, phase in rows.values_list("id", "tone", "phase")
    ]


def opened_app_since(user_id, since: datetime) -> bool:
    """
    Did the student open the app at or after `since` (the start of their local day)? Two signals, and either counts:
    the last visit the web reports when a tab is hidden (`profiles`), and the thought card, which is fetched the first
    time the student opens the home page in a day, so it also covers a tab that is still open and was never hidden.
    A message the nudge itself used is not a visit: only `inapp` rows count.
    """
    visit = profile_selectors.get_last_visit(user_id)
    if visit is not None and visit.visited_at >= since:
        return True
    return MessageShown.objects.filter(user_id=user_id, channel=ShownChannel.INAPP, created_at__gte=since).exists()
