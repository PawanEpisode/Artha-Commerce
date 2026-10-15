"""Request parsing and response shapes of the planner endpoints (`docs/F-13-API-CONTRACT.md`, "Planner")."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from rest_framework import serializers

from . import planner_selectors
from .models import Milestone, ReplanEvent, StudyPlan
from .planner import constants as pc

PLANNER_VERSION = 1


class CreatePlanSerializer(serializers.Serializer):
    daily_minutes = serializers.IntegerField(
        required=False, min_value=pc.DAILY_MINUTES_MIN, max_value=pc.DAILY_MINUTES_MAX
    )


class ReplanSerializer(serializers.Serializer):
    pass


class ChooseOptionSerializer(serializers.Serializer):
    event_id = serializers.UUIDField()
    option = serializers.ChoiceField(choices=pc.OPTION_CHOICES)


class EventsQuerySerializer(serializers.Serializer):
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=pc.RESULT_EVENTS)


def _iso(value: date | datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def next_replan_on(plan: StudyPlan, today: date, last_on: date | None) -> str | None:
    """The next day an automatic re-plan can happen: the next Monday, no sooner than the minimum gap after the last re-plan."""
    earliest = today + timedelta(days=1)
    if last_on is not None:
        earliest = max(earliest, last_on + timedelta(days=pc.REPLAN_MIN_GAP_DAYS))
    ahead = (pc.REPLAN_WEEKDAY - earliest.weekday()) % 7
    day = earliest + timedelta(days=ahead)
    return day.isoformat() if day < plan.exam_date else None


def milestone_dict(m: Milestone, today: date) -> dict:
    overdue = (today - m.target_date).days if m.status in pc.OPEN_MILESTONE_STATUSES and m.target_date < today else 0
    return {
        "id": str(m.id),
        "kind": m.kind,
        "subject_key": m.subject_key,
        "subject_id": str(m.subject_id) if m.subject_id else None,
        "subject_name": m.subject.name if m.subject_id and m.subject else None,
        "target_date": m.target_date.isoformat(),
        "original_target_date": m.original_target_date.isoformat(),
        "moved_days": (m.target_date - m.original_target_date).days,
        "overdue_days": overdue,
        "remaining_minutes": m.remaining_minutes,
        "status": m.status,
        "done_at": _iso(m.done_at),
    }


def event_dict(event: ReplanEvent) -> dict:
    return {
        "id": str(event.id),
        "trigger": event.trigger,
        "health_before": event.health_before,
        "health_after": event.health_after,
        "shortfall_before": event.shortfall_before,
        "shortfall_after": event.shortfall_after,
        "moved_count": event.moved_count,
        "option_chosen": event.option_chosen,
        "moved": event.summary.get("moved", []),
        "options": event.summary.get("options", []),
        "created_at": event.created_at.isoformat(),
    }


def plan_payload(
    plan: StudyPlan, *, today: date, tz: str, now: datetime, last_replanned_on: date | None = None
) -> dict:
    pending = planner_selectors.pending_event(plan)
    latest = planner_selectors.latest_event(plan)
    return {
        "version": PLANNER_VERSION,
        "server_time": now.isoformat(),
        "id": str(plan.id),
        "enrollment_id": str(plan.enrollment_id),
        "exam_date": plan.exam_date.isoformat(),
        "daily_minutes": plan.daily_minutes,
        "health": plan.health,
        "capacity_minutes": plan.capacity_minutes,
        "remaining_minutes": plan.remaining_minutes,
        "shortfall_minutes": plan.shortfall_minutes,
        "reading_deadline": _iso(plan.reading_deadline),
        "revise_until": _iso(plan.revise_until),
        "health_checked_at": _iso(plan.health_checked_at),
        "last_replanned_at": _iso(plan.last_replanned_at),
        "next_replan_on": next_replan_on(plan, today, last_replanned_on),
        "replan_no": plan.replan_no,
        "plan_version": plan.version,
        "tz": tz,
        "milestones": [milestone_dict(m, today) for m in planner_selectors.milestones_of(plan)],
        "pending": event_dict(pending) if pending is not None else None,
        "latest_replan": event_dict(latest) if latest is not None else None,
    }


def events_payload(events: list[ReplanEvent], *, now: datetime) -> dict:
    return {"version": PLANNER_VERSION, "server_time": now.isoformat(), "events": [event_dict(e) for e in events]}
