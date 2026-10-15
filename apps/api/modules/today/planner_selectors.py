"""
Read-only queries for the R2 study planner. Every function takes `user_id` and filters on it. Nothing here writes.
"""

from __future__ import annotations

from datetime import date

from django.db.models import QuerySet

from . import selectors
from .adapters import tracking as tracking_adapter
from .models import Milestone, ReplanEvent, StudyPlan
from .planner import constants as pc


def active_plan(user_id, enrollment_id=None) -> StudyPlan | None:
    """The student's active plan (one per enrolment). Without `enrollment_id`, the newest active one."""
    rows = StudyPlan.objects.filter(user_id=user_id, status="active")
    if enrollment_id is not None:
        rows = rows.filter(enrollment_id=enrollment_id)
    return rows.order_by("-created_at").first()


def milestones_of(plan: StudyPlan) -> QuerySet[Milestone]:
    return plan.milestones.select_related("subject").order_by("sort_order", "target_date")


def open_milestones(plan: StudyPlan) -> QuerySet[Milestone]:
    return milestones_of(plan).filter(status__in=pc.OPEN_MILESTONE_STATUSES)


def events_of(plan: StudyPlan, limit: int = 20) -> list[ReplanEvent]:
    return list(plan.replan_events.order_by("-created_at", "-id")[:limit])


def latest_event(plan: StudyPlan) -> ReplanEvent | None:
    return plan.replan_events.order_by("-created_at", "-id").first()


def event_of(user_id, event_id) -> ReplanEvent | None:
    return ReplanEvent.objects.filter(user_id=user_id, pk=event_id).select_related("plan").first()


def pending_event(plan: StudyPlan) -> ReplanEvent | None:
    """The latest re-plan, when the student still has to choose an option for it."""
    event = latest_event(plan)
    return event if event is not None and event.option_chosen is None and event.summary.get("options") else None


def active_days(user_id, since: date, until: date) -> set[date]:
    """Local days in `[since, until]` with tracked time or a done task: what "a missed day" is measured against."""
    if until < since:
        return set()
    return tracking_adapter.days_with_time(user_id, since, until) | selectors.done_days(user_id, since, until)
