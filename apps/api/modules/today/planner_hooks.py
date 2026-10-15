"""
What the planner listens to (installed from `TodayConfig.ready()`): reading finished (a paper's milestone is done that day), a new
exam date or another scheme (the plan follows the course). Each handler does nothing for a student without a plan, and a failure
never reaches the module that announced the event (`core.events.emit` isolates it).
"""

from __future__ import annotations

from core import events

from . import planner_services

COVERAGE_EVENT = "coverage_event_recorded"
EXAM_CHANGED = "enrollment_exam_changed"
SCHEME_CHANGED = "enrollment_scheme_changed"
READING_TYPES = ("topic_done", "practice_done", "excluded", "included")


def on_coverage_event(**payload) -> None:
    if payload.get("type") in READING_TYPES and payload.get("user_id"):
        planner_services.mark_reading_done(payload["user_id"])


def on_course_changed(**payload) -> None:
    if payload.get("user_id"):
        planner_services.sync_enrollment(payload["user_id"])


def install() -> None:
    events.subscribe(COVERAGE_EVENT, on_coverage_event)
    events.subscribe(EXAM_CHANGED, on_course_changed)
    events.subscribe(SCHEME_CHANGED, on_course_changed)
