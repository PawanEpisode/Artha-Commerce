"""
How a task completes without the student touching it (PRD 5.3): an owning module announces what happened, Today's inline subscriber
finds the open tasks the event could belong to, asks the provider's pure completion rule, writes idempotent evidence, and completes
the task when the rule says done or the progress reaches the target. `reconcile_plan` does the same from the other side: it asks
the provider's source of truth about open tasks, for events that never arrived (offline, a missed delivery).

Safe to repeat and to reorder: evidence is unique per (task, event name, event key), progress is recomputed from the evidence, done
is terminal. The time the event happened (not the time it arrived) decides which day's tasks it can complete, with the late-night
grace: an event up to 03:00 local still completes yesterday's open task, even one the day sweep already expired.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from core import events

from . import actions, registry, services
from .adapters import tracking as tracking_adapter
from .domain import constants as c
from .models import Task, TaskEvidence

logger = logging.getLogger(__name__)

RECONCILE_EVERY_SECONDS = (
    30  # `open/` is called on every focus; the source of truth is asked at most this often per student and day
)
_handlers: dict[str, object] = {}


# ---- subscribing ------------------------------------------------------------------------------------------------------------


def _handler_for(name: str):
    """One stable function per event name, so `events.subscribe` stays idempotent."""
    if name not in _handlers:

        def handler(**payload):
            handle(name, payload)

        handler.__name__ = f"today_complete_on_{name}"
        _handlers[name] = handler
    return _handlers[name]


def subscribe_all() -> None:
    for name in registry.completion_event_names():
        events.subscribe(name, _handler_for(name))


def install() -> None:
    """From `TodayConfig.ready()`. Providers register from other apps' `ready()` in any order, so we also listen to registrations."""
    registry.add_register_hook(subscribe_all)
    subscribe_all()


# ---- an event arrives -------------------------------------------------------------------------------------------------------


def _parse(name: str, payload: dict) -> registry.Event | None:
    try:
        key = str(payload.get("event_id") or payload["key"])
        occurred = payload.get("occurred_at")
        when = datetime.fromisoformat(occurred) if isinstance(occurred, str) else (occurred or timezone.now())
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return registry.Event(
            name=name, key=key[:120], user_id=UUID(str(payload["user_id"])), occurred_at=when, payload=payload
        )
    except (KeyError, ValueError, TypeError):
        logger.warning("today: event %s without a usable user, key or time was ignored", name)
        return None


def handle(name: str, payload: dict) -> int:
    event = _parse(name, payload)
    return complete_from_event(event) if event else 0


def _candidate_days(event: registry.Event, tz: str) -> tuple[date, list[date]]:
    """The local day the event happened on, plus the day before it while the event is inside the late-night grace."""
    local = event.occurred_at.astimezone(ZoneInfo(tz))
    day = local.date()
    minutes = local.hour * 60 + local.minute
    return day, [day, day - timedelta(days=1)] if minutes < c.GRACE_MINUTES else [day]


def complete_from_event(event: registry.Event) -> int:
    """How many tasks this event changed (progress or done). Never raises: a rule that fails is skipped and logged."""
    specs = {s.name: s for s in registry.providers() if any(r.event_name == event.name for r in s.completion)}
    if not specs:
        return 0
    tz = tracking_adapter.timezone_of(event.user_id)
    day, days = _candidate_days(event, tz)
    rows = Task.objects.filter(
        user_id=event.user_id, provider__in=list(specs), local_date__in=days, deleted_at__isnull=True
    ).filter(
        Q(state__in=(*c.OPEN_STATES, "skipped", "snoozed"))
        | Q(state="expired", end_reason="day_ended", local_date__lt=day)
    )
    changed = 0
    for task in rows:
        view = actions.view_of(task)
        for rule in specs[task.provider].completion:
            if rule.event_name != event.name:
                continue
            try:
                match = rule.match(event, view)
            except Exception:  # noqa: BLE001 - a provider's rule never breaks the module that announced the event
                logger.exception("today: completion rule of %s failed", task.provider)
                continue
            if match is None:
                continue
            if apply_evidence(
                event.user_id,
                task.id,
                event_name=event.name,
                event_key=match.evidence_key or event.key,
                delta=match.delta,
                completes=match.done,
                occurred_at=event.occurred_at,
            ):
                changed += 1
            break
    return changed


# ---- the one place evidence is applied --------------------------------------------------------------------------------------


def apply_evidence(
    user_id,
    task_id,
    *,
    event_name: str,
    event_key: str,
    delta: int,
    completes: bool,
    occurred_at: datetime,
    now: datetime | None = None,
) -> bool:
    """
    Records that one event contributed to one task and completes it when due. Returns False for a replay (the same event key for
    the same task): nothing at all changes. Progress is the sum of all evidence deltas, capped at the target, so a late or
    reordered event gives the same result as an on-time one.
    """
    now = now or timezone.now()
    try:
        with transaction.atomic():
            return _apply(
                user_id,
                task_id,
                event_name=event_name,
                event_key=event_key,
                delta=delta,
                completes=completes,
                occurred_at=occurred_at,
                now=now,
            )
    except (
        IntegrityError
    ):  # a constraint the rules above should make impossible: refuse the evidence, keep the plan intact
        logger.warning("today: evidence for task %s violated a constraint and was dropped", task_id, exc_info=True)
        return False


def _apply(user_id, task_id, *, event_name, event_key, delta, completes, occurred_at, now) -> bool:
    try:
        plan, task = actions.locked(user_id, task_id)
    except actions.TaskNotFound:
        return False
    if task.state == "expired" and task.end_reason != "day_ended":
        return False  # a replaced suggestion is gone; only a day that ended may still be completed (the grace)
    try:
        with transaction.atomic():
            TaskEvidence.objects.create(
                task=task,
                user_id=user_id,
                event_name=event_name,
                event_key=event_key,
                delta=max(int(delta), 0),
                completes=bool(completes),
                occurred_at=occurred_at,
            )
    except IntegrityError:
        return False
    total = TaskEvidence.objects.filter(task=task).aggregate(n=Sum("delta"))["n"] or 0
    progress = min(total, task.target_value) if task.target_value else total
    reached = bool(completes) or (task.target_value is not None and progress >= task.target_value)
    task.progress_value = progress
    if reached and task.state != "done":
        was = task.state
        actions._enter(task, "done", now, None)
        task.prev_state = was if was in c.OPEN_STATES else "suggested"
        task.completed_at, task.completed_via = now, "event"
        actions._finish(plan, task)
        actions._emit(
            actions.TASK_COMPLETED,
            user_id=str(user_id),
            task_id=str(task.id),
            kind=task.kind,
            provider=task.provider,
            via="event",
            est_minutes=task.est_minutes,
            position=task.position,
            first_of_day=plan.done_count == 1,
            manual_action_ran=False,
        )
    else:
        task.version += 1
        task.save()
        services.settle(plan)
    return True


# ---- reconcile --------------------------------------------------------------------------------------------------------------


def reconcile_plan(plan, *, now: datetime | None = None, force: bool = False) -> int:
    """Asks every provider that can answer about the plan's open tasks. At most every 30 seconds per student and day."""
    now = now or timezone.now()
    key = f"today:reconcile:{plan.user_id}:{plan.local_date.isoformat()}"
    if not force and not cache.add(key, 1, RECONCILE_EVERY_SECONDS):
        return 0
    by_provider: dict[str, list[Task]] = defaultdict(list)
    for task in Task.objects.filter(plan=plan, state__in=c.OPEN_STATES, origin="provider", deleted_at__isnull=True):
        by_provider[task.provider].append(task)
    changed = 0
    for name, tasks in by_provider.items():
        spec = registry.get_provider(name)
        if spec is None or spec.reconcile is None:
            continue
        try:
            found = spec.reconcile(plan.user_id, [actions.view_of(t) for t in tasks], plan.local_date)
        except Exception:  # noqa: BLE001 - a provider that cannot answer leaves its tasks as they are
            logger.exception("today: reconcile of %s failed", name)
            continue
        by_id = {t.id: t for t in tasks}
        for task_id, evidence in found.items():
            task = by_id.get(task_id)
            if task is None:
                continue
            delta = max((evidence.progress or 0) - task.progress_value, 0) if evidence.progress is not None else 0
            if apply_evidence(
                plan.user_id,
                task_id,
                event_name="reconcile",
                event_key=evidence.key[:120],
                delta=delta,
                completes=evidence.done,
                occurred_at=now,
                now=now,
            ):
                changed += 1
    return changed
