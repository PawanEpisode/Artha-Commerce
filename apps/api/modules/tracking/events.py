"""
Announces stopwatch and daily-goal changes to whoever cares (X-01.1 PRD C1, FR-N19). `tracking` owns the facts and stays
unaware of its consumers: it only says what happened through `core.events`; `notifications` subscribes. This is the one
announcing file for the module, with two decorators:

`announces_stopwatch` wraps every public action that can change the live stopwatch. After the action the stopwatch is read
again and, if its identity (`client_id`, `version`) differs from before, exactly one `stopwatch_changed` is emitted once
the transaction has committed (a rolled-back action announces nothing). A retried start, a heartbeat or a pause of a
paused stopwatch changes nothing and is silent. The lazy "Still studying?" settle is covered because the check looks at
the result, not at which branch produced it.
  Payload (plain values, no secrets): `user_id`, `active`, `client_id`, `version`, `started_at`, `paused`,
  `paused_total_seconds`, `at` (the server time of the announcement, so a consumer judges "is this still ahead" on the same
  clock as the stopwatch). When the stopwatch is gone (`active` False) only `user_id` and `at` are meaningful.

`announces_goal` wraps every public action that can raise today's counted time. It compares the student's overall daily
goal for today before and after the action and, when the goal went from not met to met, emits one `goal_reached` after
commit. Actions nested inside another announcing action report nothing themselves: the outer one compares the whole
change, so one request announces at most once. Concurrent writers may both see "not met" and both announce; that is
harmless because a consumer dedupes on the local date.
  Payload: `user_id`, `local_date` (ISO), `done_seconds`, `goal_minutes`, `at`.
"""

from __future__ import annotations

import contextvars
import functools
from collections.abc import Callable
from datetime import datetime
from typing import Any

from django.db import transaction

from core import events as bus

from . import selectors
from .domain import durations
from .models import ActiveStopwatch

STOPWATCH_CHANGED = "stopwatch_changed"
GOAL_REACHED = "goal_reached"

_Identity = tuple[str, int] | None


def _now() -> datetime:
    # Resolved at call time: `services` imports this file, and tests pin `services._now`.
    from . import services

    return services._now()


# --- Stopwatch -----------------------------------------------------------------------------------------------------
def _identity(sw: ActiveStopwatch | None) -> _Identity:
    return (str(sw.client_id), sw.version) if sw else None


def stopwatch_snapshot(user_id, sw: ActiveStopwatch | None, at: datetime) -> dict[str, Any]:
    """The payload for the current state of a student's stopwatch (None means no stopwatch)."""
    if sw is None:
        return {"user_id": str(user_id), "active": False, "at": at}
    return {
        "user_id": str(user_id),
        "active": True,
        "client_id": str(sw.client_id),
        "version": sw.version,
        "started_at": sw.started_at,
        "paused": sw.paused_at is not None,
        "paused_total_seconds": sw.paused_total_seconds,
        "at": at,
    }


def announces_stopwatch(action: Callable) -> Callable:
    """Wrap a service action `action(user_id, ...)`; it must run inside `transaction.atomic` (the lock needs one)."""

    @functools.wraps(action)
    def wrapper(user_id, *args, **kwargs):
        before = _identity(ActiveStopwatch.objects.select_for_update().filter(pk=user_id).first())
        result = action(user_id, *args, **kwargs)
        after = ActiveStopwatch.objects.filter(pk=user_id).first()
        if _identity(after) != before:
            payload = stopwatch_snapshot(user_id, after, _now())
            transaction.on_commit(lambda: bus.emit(STOPWATCH_CHANGED, **payload))
        return result

    wrapper.announces_stopwatch_changes = True  # read by the test that guards every public action
    return wrapper


# --- Daily goal ----------------------------------------------------------------------------------------------------
_announcing: contextvars.ContextVar[bool] = contextvars.ContextVar("tracking_goal_announcing", default=False)


def _local_today(user_id, now: datetime):
    return durations.local_date(now, selectors.settings_or_default(user_id).tz)


def announces_goal(action: Callable) -> Callable:
    """Wrap a service action `action(user_id, ...)` that can raise today's counted time; run it inside a transaction."""

    @functools.wraps(action)
    def wrapper(user_id, *args, **kwargs):
        if _announcing.get():  # nested: the outer action compares the whole change
            return action(user_id, *args, **kwargs)
        token = _announcing.set(True)
        try:
            day = _local_today(user_id, _now())
            before = selectors.daily_progress(user_id, day)
            result = action(user_id, *args, **kwargs)
            after = selectors.daily_progress(user_id, day)
        finally:
            _announcing.reset(token)
        if after.met and not before.met:
            payload = {
                "user_id": str(user_id),
                "local_date": day.isoformat(),
                "done_seconds": after.done_seconds,
                "goal_minutes": after.goal_minutes,
                "at": _now(),
            }
            transaction.on_commit(lambda: bus.emit(GOAL_REACHED, **payload))
        return result

    wrapper.announces_goal_reached = True  # read by the test that guards every public action
    return wrapper
