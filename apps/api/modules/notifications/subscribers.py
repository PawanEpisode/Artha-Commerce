"""
Listeners for events other modules publish. Tiny on purpose: validate the payload, ask the flags, call the job service.
Nothing here judges whether to notify; that happens when the job fires, from the facts at that moment.

`timer_changed` (from `focus`): the timer moved, so the end it announced earlier may no longer be real.
  * a running timer with an end still ahead gets exactly one job for its (timer, version), the older ones are cancelled;
  * a paused, ended, replaced or discarded timer just cancels what was waiting;
  * `away_pending` changes nothing: it is the lazy settle noticing a round ended while the student was away, and the
    job for that end must still fire (the alert is the point). The judgement recognises that case.
`stopwatch_changed` (from `tracking`): the stopwatch moved, so the "still running" moment it announced may be gone.
  * a running stopwatch whose counted time will reach the mark gets exactly one job for its (stopwatch, version), planned
    for the instant the counted time reaches three hours (its start plus the pauses it has had plus three hours); older
    ones are cancelled. A pause, resume, retag or idle pause changes the version, so the job is planned again;
  * a paused, stopped or erased stopwatch, or one already past the mark, just cancels what was waiting. "Once per session"
    comes from the dedupe key (`stopwatch_long:{client_id}`), not from this listener.

`goal_reached` (from `tracking`): today's goal went from not met to met. The alert is created here (once per local date,
by its dedupe key) and handed to a `deliver_deferred` job due in a moment, so the push is sent by the queue or the sweep
and never inside the student's own request. Quiet hours, the cap and the expiry are judged when that job fires.

A queue problem is absorbed inside `scheduling.planning`; the sweep fires any job whose message never arrived.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from core import events
from modules.focus.events import TIMER_CHANGED
from modules.tracking.domain.judgement import reaches_at
from modules.tracking.events import GOAL_REACHED, STOPWATCH_CHANGED

from . import flags
from .domain import tracker_alerts
from .logs import log_event
from .scheduling import jobs
from .services import notify as notify_service

ON_BREAK = "break_over"
ON_FOCUS = "timer_end"
IMMEDIATE_DELAY = timedelta(
    seconds=2
)  # a queue may refuse a "not before" that has already passed, so aim a moment ahead


def _event_for(phase: str) -> str:
    return ON_FOCUS if phase == "focus" else ON_BREAK


def on_timer_changed(
    *,
    user_id: str,
    active: bool = False,
    client_id: str | None = None,
    version: int | None = None,
    phase: str | None = None,
    ends_at: datetime | None = None,
    paused: bool = False,
    overtime: bool = False,
    round: int | None = None,  # noqa: A002 - the payload key
    minutes: int | None = None,
    subject_name: str | None = None,
    break_minutes: int | None = None,
    next_round: int | None = None,
    away_pending: bool = False,
    at: datetime | None = None,
    **_ignored,
) -> None:
    if not flags.master_enabled():  # the hard stop: nothing is planned or cancelled while the feature is off
        return
    if active and away_pending:
        return
    student = UUID(user_id)

    keep = None
    if active and not paused and ends_at is not None and phase and client_id and version is not None:
        # An end that has already passed (a round running on in overtime) was announced when it was ahead.
        ahead = at is None or ends_at > at
        event = _event_for(phase)
        if ahead and not flags.event_disabled(event) and flags.sending_enabled(student):
            jobs.plan_timer_end(
                student,
                client_id=client_id,
                version=version,
                fire_at=ends_at,
                context={
                    "phase": phase,
                    "round_number": round,
                    "minutes": minutes,
                    "subject_name": subject_name,
                    "break_minutes": break_minutes,
                    "next_round": next_round,
                    "overtime": overtime,
                },
            )
            keep = (client_id, version)
    cancelled = jobs.cancel_for_timer(student, keep=keep)
    if cancelled:
        log_event(logging.INFO, "job_cancelled", kind="timer_end", count=cancelled)


def on_stopwatch_changed(
    *,
    user_id: str,
    active: bool = False,
    client_id: str | None = None,
    version: int | None = None,
    started_at: datetime | None = None,
    paused: bool = False,
    paused_total_seconds: int = 0,
    at: datetime | None = None,
    **_ignored,
) -> None:
    if not flags.master_enabled():
        return
    student = UUID(user_id)

    keep = None
    if active and not paused and client_id and version is not None and started_at is not None:
        fire_at = reaches_at(started_at, paused_total_seconds, tracker_alerts.stopwatch_long_after_seconds())
        ahead = at is None or fire_at > at  # past the mark already: the alert was due earlier and is not owed now
        if ahead and not flags.event_disabled("stopwatch_long") and flags.sending_enabled(student):
            jobs.plan_stopwatch_long(student, client_id=client_id, version=version, fire_at=fire_at, context={})
            keep = (client_id, version)
    cancelled = jobs.cancel_for_stopwatch(student, keep=keep)
    if cancelled:
        log_event(logging.INFO, "job_cancelled", kind="stopwatch_long", count=cancelled)


def on_goal_reached(
    *,
    user_id: str,
    local_date: str,
    done_seconds: int,
    goal_minutes: int,
    at: datetime | None = None,
    **_ignored,
) -> None:
    if not flags.master_enabled() or flags.event_disabled("goal_reached"):
        return
    student = UUID(user_id)
    if not flags.sending_enabled(student):
        return
    notification, created = notify_service.create_notification(
        student,
        "goal_reached",
        context={"local_date": local_date, "studied_minutes": done_seconds // 60, "goal_minutes": goal_minutes},
        dedupe_parts={"local_date": local_date},
        now=at,
    )
    if created:  # a second announcement the same day (an undo, a second writer) finds the alert and does nothing
        jobs.plan_deferred(notification, (at or notification.created_at) + IMMEDIATE_DELAY)


def register() -> None:
    """Idempotent (`core.events.subscribe` ignores a repeat), so `AppConfig.ready` may run twice."""
    events.subscribe(TIMER_CHANGED, on_timer_changed)
    events.subscribe(STOPWATCH_CHANGED, on_stopwatch_changed)
    events.subscribe(GOAL_REACHED, on_goal_reached)
