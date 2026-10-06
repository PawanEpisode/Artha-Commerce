"""
Announces timer changes to whoever cares (PRD C1, FR-N19). `focus` owns the fact and stays unaware of its consumers:
it only says "the timer changed" through `core.events`; `notifications` subscribes. This is the one announcing function
for the module.

Every public service action that can change the live timer is wrapped with `announces`. After the action the timer is
read again and, if its identity (`client_id`, `version`) differs from before, exactly one `timer_changed` is emitted
once the transaction has committed (a rolled-back action announces nothing). That covers every way the timer moves,
including the lazy settle that happens when a request reads it, because the check looks at the result and not at which
branch produced it. An action that changes nothing (a retried start, a heartbeat, a pause of a paused timer) is silent.

Payload (small, plain values, no secrets): `user_id`, `active`, `client_id`, `version`, `phase`, `ends_at`, `paused`,
`overtime`, `round`, `minutes`, `subject_name`, `break_minutes`, `next_round`, `away_pending`, and `at` (the server time
of the announcement, so a consumer judges "has the end already passed" on the same clock as the timer). When the timer
is gone (`active` False) only `user_id` and `at` are meaningful.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from django.db import transaction

from core import events as bus
from modules.tracking import services as tracking

from . import selectors
from .domain import timing
from .models import ActiveTimer

TIMER_CHANGED = "timer_changed"

_Identity = tuple[str, int] | None


def _identity(timer: ActiveTimer | None) -> _Identity:
    return (str(timer.client_id), timer.version) if timer else None


def snapshot(user_id, timer: ActiveTimer | None) -> dict[str, Any]:
    """The payload for the current state of a student's timer (None means no timer)."""
    at = tracking._now()
    if timer is None:
        return {"user_id": str(user_id), "active": False, "at": at}
    on_break = timer.phase != "focus"
    away = timer.away_pending
    return {
        "user_id": str(user_id),
        "active": True,
        "client_id": str(timer.client_id),
        "version": timer.version,
        "phase": timer.phase,
        "ends_at": selectors.live_end_at(timer),
        "paused": timer.paused_at is not None,
        "overtime": timer.phase == "focus" and timer.overtime_enabled and not away,
        "round": timer.round_number,
        "minutes": timer.planned_seconds // 60,
        "subject_name": timer.subject.name if timer.subject_id else None,
        "break_minutes": None
        if on_break
        else (
            timer.long_break_minutes
            if timing.break_after(timer.round_number, timer.rounds_before_long) == "long_break"
            else timer.short_break_minutes
        ),
        "next_round": (1 if timer.phase == "long_break" else timer.round_number + 1) if on_break else None,
        "away_pending": away,
        "at": at,
    }


def announces(action: Callable) -> Callable:
    """Wrap a service action `action(user_id, ...)`; it must run inside `transaction.atomic` (the lock needs one)."""

    @functools.wraps(action)
    def wrapper(user_id, *args, **kwargs):
        before = _identity(ActiveTimer.objects.select_for_update().filter(pk=user_id).first())
        result = action(user_id, *args, **kwargs)
        after = ActiveTimer.objects.select_related("subject").filter(pk=user_id).first()
        if _identity(after) != before:
            payload = snapshot(user_id, after)
            transaction.on_commit(lambda: bus.emit(TIMER_CHANGED, **payload))
        return result

    wrapper.announces_timer_changes = True  # read by the test that guards every public action
    return wrapper
