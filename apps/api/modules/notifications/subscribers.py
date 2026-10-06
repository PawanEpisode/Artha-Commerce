"""
Listeners for events other modules publish. Tiny on purpose: validate the payload, ask the flags, call the job service.
Nothing here judges whether to notify; that happens when the job fires, from the facts at that moment.

`timer_changed` (from `focus`): the timer moved, so the end it announced earlier may no longer be real.
  * a running timer with an end still ahead gets exactly one job for its (timer, version), the older ones are cancelled;
  * a paused, ended, replaced or discarded timer just cancels what was waiting;
  * `away_pending` changes nothing: it is the lazy settle noticing a round ended while the student was away, and the
    job for that end must still fire (the alert is the point). The judgement recognises that case.
A queue problem is absorbed inside `scheduling.jobs`; the sweep fires any job whose message never arrived.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from core import events
from modules.focus.events import TIMER_CHANGED

from . import flags
from .logs import log_event
from .scheduling import jobs

ON_BREAK = "break_over"
ON_FOCUS = "timer_end"


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


def register() -> None:
    """Idempotent (`core.events.subscribe` ignores a repeat), so `AppConfig.ready` may run twice."""
    events.subscribe(TIMER_CHANGED, on_timer_changed)
