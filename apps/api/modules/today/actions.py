"""
What a student does to a task (PRD 5.2, ERD 3.2, 3.5): start, complete, skip, snooze, swap, undo, their own tasks, and
regenerate. Every action runs in one transaction that locks the plan row, then the task row (always in that order, so two actions
never deadlock), applies the state machine in `domain/states.py`, and recounts the plan from its rows.

Rules that hold for every action:

- Replays are free. A repeated `client_id` returns the task as it is and writes nothing; so does an action whose result already
  holds (completing a done task, skipping a skipped one).
- Done beats everything. A skip, snooze or swap that arrives after the task is done (a stale offline write) gets 409
  `state_conflict` with the current task. A completion arriving at a skipped or snoozed task wins.
- Between two open states the later `client_ts` wins; the loser gets 409 `state_conflict`.
- Counters are recomputed from the rows (`services.settle`), never incremented.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.models import F, Max
from django.utils import timezone

from core import events
from core.errors import QuotaExceeded

from . import generation, registry, services
from .adapters import coverage as coverage_adapter
from .domain import constants as c
from .domain import states
from .domain.week import day_closing
from .errors import (
    InvalidDate,
    InvalidScope,
    InvalidTransitionError,
    NoAlternative,
    PlanChanged,
    PlanNotGenerated,
    ProviderTaskReadOnly,
    StateConflict,
    TaskNotFound,
    UndoExpiredError,
)
from .models import DayPlan, Task

logger = logging.getLogger(__name__)

# Domain events (names are `noun_verb`; the web's analytics events of the same names are sent by the web or by a subscriber).
TASK_COMPLETED = "today_task_completed"
TASK_SKIPPED = "today_task_skipped"
TASK_SNOOZED = "today_task_snoozed"
TASK_SWAPPED = "today_task_swapped"
PLAN_REGENERATED = "today_plan_regenerated"
DAY_COMPLETED = "today_day_completed"


@dataclass(frozen=True)
class StartResult:
    task: Task
    link: dict


@dataclass(frozen=True)
class SkipResult:
    task: Task
    suppressed_days: int | None


@dataclass(frozen=True)
class SwapResult:
    old: Task
    new: Task


@dataclass(frozen=True)
class DeleteResult:
    task: Task
    undo_until: datetime


# ---- locking and shared steps -----------------------------------------------------------------------------------------------


def locked(user_id, task_id, *, include_deleted: bool = False) -> tuple[DayPlan, Task]:
    """
    The task's plan, then the task, both `FOR UPDATE`. Another student's id, an unknown id and a deleted task are all
    `TaskNotFound`. An own task may move to another plan between the unlocked read and the lock; then we start over.
    """
    for _ in range(3):
        plan_id = Task.objects.filter(pk=task_id, user_id=user_id).values_list("plan_id", flat=True).first()
        if plan_id is None:
            raise TaskNotFound
        plan = DayPlan.objects.select_for_update().get(pk=plan_id)
        task = (
            Task.objects.select_for_update(of=("self",))
            .select_related("subject")
            .filter(pk=task_id, user_id=user_id)
            .first()
        )
        if task is None:
            raise TaskNotFound
        if task.plan_id != plan.pk:
            continue
        if task.deleted_at is not None and not include_deleted:
            raise TaskNotFound
        return plan, task
    raise TaskNotFound  # pragma: no cover - three moves in a row is not a thing a student can do


def view_of(task: Task) -> registry.TaskView:
    return registry.TaskView(
        id=task.id,
        kind=task.kind,
        dedupe_key=task.dedupe_key,
        local_date=task.local_date,
        state=task.state,
        subject_id=task.subject_id,
        chapter_id=task.chapter_id,
        target_value=task.target_value,
        progress_value=task.progress_value,
        payload=dict(task.payload or {}),
    )


def _conflict(task: Task) -> StateConflict:
    from .serializers import task_dict  # local: serializers read models only, but keep the import graph one way

    return StateConflict(
        extra={"task": task_dict(task), "allowed": list(states.allowed_actions(task.state, origin=task.origin))}
    )


def _invalid(task: Task, action: str, error: states.InvalidTransition | None = None) -> InvalidTransitionError:
    allowed = error.allowed if error else states.allowed_actions(task.state, origin=task.origin)
    return InvalidTransitionError(
        f"You cannot {action.replace('_', ' ')} a task that is {task.state}.",
        extra={"state": task.state, "action": action, "allowed": list(allowed)},
    )


def _replay(task: Task, client_id) -> bool:
    return client_id is not None and task.last_client_id == client_id


def _check_order(task: Task, action: str, now: datetime, client_ts: datetime | None) -> None:
    """Cross-device rule (ERD 3.5): done is terminal, otherwise the later `client_ts` wins."""
    ts = (client_ts or now).timestamp()
    if not states.incoming_wins(task.state, action, current_changed_ts=task.state_changed_at.timestamp(), client_ts=ts):
        raise _conflict(task)


def _enter(task: Task, new_state: str, now: datetime, client_id) -> None:
    """Common bookkeeping of a state change; the caller sets the columns that belong to the new state."""
    task.prev_state = task.state
    task.state = new_state
    task.state_changed_at = now
    task.last_client_id = client_id
    task.version += 1
    task.completed_at = task.completed_via = task.skip_reason = task.end_reason = task.snoozed_until = None


def _finish(plan: DayPlan, task: Task) -> None:
    """Save the task and recount the plan; announce a day that just became finished."""
    before = day_closing(open_count=plan.open_count, done_count=plan.done_count, skipped_count=plan.skipped_count)
    task.save()
    services.settle(plan)
    after = day_closing(open_count=plan.open_count, done_count=plan.done_count, skipped_count=plan.skipped_count)
    if after is not None and before is None:
        payload = dict(
            user_id=str(plan.user_id),
            date=plan.local_date.isoformat(),
            done=plan.done_count,
            skipped=plan.skipped_count,
            planned=plan.planned_count,
            completed=after == "celebrate",
        )
        transaction.on_commit(lambda: events.emit(DAY_COMPLETED, **payload))


def _emit(name: str, **payload) -> None:
    transaction.on_commit(lambda: events.emit(name, **payload))


# ---- start, complete, skip, snooze, undo ------------------------------------------------------------------------------------


def start_task(user_id, task_id, *, client_id, client_ts=None, now: datetime | None = None) -> StartResult:
    now = now or timezone.now()
    with transaction.atomic():
        plan, task = locked(user_id, task_id)
        link = {"path": task.link_path, "search": dict(task.link_search or {})}
        if _replay(task, client_id) or task.state in ("accepted", "done"):
            return StartResult(task, link)  # starting a task that is under way or finished changes nothing
        _check_order(task, "start", now, client_ts)
        try:
            new = states.transition(task.state, "start", prev_state=task.prev_state, origin=task.origin)
        except states.InvalidTransition as error:
            raise _invalid(task, "start", error) from error
        _enter(task, new, now, client_id)
        _finish(plan, task)
        return StartResult(task, link)


def complete_task(
    user_id,
    task_id,
    *,
    client_id,
    client_ts: datetime | None = None,
    run_manual_action: bool = False,
    now: datetime | None = None,
) -> Task:
    """
    The student's tick. Idempotent: a done task stays as it is, whoever completed it. A task that was skipped or snoozed on another
    device is completed anyway (done beats a stale skip). With `run_manual_action` the provider's action (for a revision: also log
    it) runs first, once, inside a savepoint; its failure never blocks the tick.
    """
    now = now or timezone.now()
    with transaction.atomic():
        plan, task = locked(user_id, task_id)
        if _replay(task, client_id) or task.state == "done":
            return task
        if task.state in ("skipped", "snoozed"):
            new = "done"  # the stale-skip rule: outside the table on purpose, so a completion never loses
        else:
            try:
                new = states.transition(task.state, "complete_manual", prev_state=task.prev_state, origin=task.origin)
            except states.InvalidTransition as error:
                raise _invalid(task, "complete_manual", error) from error
        ran = False
        if run_manual_action and task.manual_action:
            found = registry.manual_action(task.manual_action.get("key", ""))
            if found is not None:
                try:
                    with transaction.atomic():
                        found[1].run(user_id, view_of(task))
                    ran = True
                except Exception:  # noqa: BLE001 - a provider's action never blocks the student's tick
                    logger.exception(
                        "today: manual action %s failed for task %s", task.manual_action.get("key"), task.id
                    )
        was = task.state
        _enter(task, new, now, client_id)
        if was in ("skipped", "snoozed"):
            task.prev_state = "suggested"  # so an undo within the window reopens it
        task.completed_at, task.completed_via = now, "manual"
        _finish(plan, task)
        _emit(
            TASK_COMPLETED,
            user_id=str(user_id),
            task_id=str(task.id),
            kind=task.kind,
            provider=task.provider,
            via="manual",
            est_minutes=task.est_minutes,
            position=task.position,
            first_of_day=plan.done_count == 1,
            manual_action_ran=ran,
        )
        return task


def _suppressed_days(task: Task) -> int | None:
    """After the third skip of the same unit of work in 14 days the provider stops offering it for 14 days."""
    if task.origin != "provider":
        return None
    since = task.local_date - timedelta(days=c.SKIP_SUPPRESS_WINDOW_DAYS)
    count = Task.objects.filter(
        user_id=task.user_id, dedupe_key=task.dedupe_key, state="skipped", origin="provider", local_date__gte=since
    ).count()
    return c.SKIP_SUPPRESS_DAYS if count >= c.SKIP_SUPPRESS_COUNT else None


def skip_task(
    user_id, task_id, *, client_id, reason: str | None = None, client_ts=None, now: datetime | None = None
) -> SkipResult:
    now = now or timezone.now()
    with transaction.atomic():
        plan, task = locked(user_id, task_id)
        if _replay(task, client_id) or task.state == "skipped":
            return SkipResult(task, _suppressed_days(task))
        _check_order(task, "skip", now, client_ts)
        try:
            new = states.transition(task.state, "skip", prev_state=task.prev_state, origin=task.origin)
        except states.InvalidTransition as error:
            raise _invalid(task, "skip", error) from error
        _enter(task, new, now, client_id)
        task.skip_reason = reason or None
        _finish(plan, task)
        suppressed = _suppressed_days(task)
        _emit(TASK_SKIPPED, user_id=str(user_id), kind=task.kind, reason=reason or "", suppressed=bool(suppressed))
        return SkipResult(task, suppressed)


def _resolve_until(until, base: date) -> date:
    """A preset name (`tomorrow`, `in_3_days`, `next_week`) or a date, counted from the task's own day."""
    if isinstance(until, str):
        if until not in c.SNOOZE_PRESET_DAYS:
            raise InvalidDate(
                "Pick a date or a preset.", extra={"until": ["Use a date or tomorrow, in_3_days, next_week."]}
            )
        return base + timedelta(days=c.SNOOZE_PRESET_DAYS[until])
    return until


def snooze_task(user_id, task_id, *, client_id, until, client_ts=None, now: datetime | None = None) -> Task:
    """
    A provider task is suppressed until the date and its provider decides whether to offer it again. A student's own task
    moves, same row, to the plan of that day (a draft if the day has none) and wakes up when the day opens.
    """
    now = now or timezone.now()
    with transaction.atomic():
        plan, task = locked(user_id, task_id)
        if _replay(task, client_id):
            return task
        until = _resolve_until(until, task.local_date)
        if not task.local_date < until <= task.local_date + timedelta(days=c.OWN_TASK_MAX_DAYS_AHEAD):
            raise InvalidDate(
                "That date is out of range.",
                extra={
                    "until": [
                        f"Use a date after {task.local_date.isoformat()} and within {c.OWN_TASK_MAX_DAYS_AHEAD} days."
                    ]
                },
            )
        if task.state == "snoozed" and task.snoozed_until == until:
            return task
        _check_order(task, "snooze", now, client_ts)
        try:
            new = states.transition(task.state, "snooze", prev_state=task.prev_state, origin=task.origin)
        except states.InvalidTransition as error:
            raise _invalid(task, "snooze", error) from error
        days = (until - task.local_date).days
        _enter(task, new, now, client_id)
        task.snoozed_until = until
        task.snooze_count += 1
        if task.origin == "user":
            task.carry_count = 0  # the student decided: the stuck counter starts again
            target = _plan_for_write(user_id, until, plan.tz)
            _check_day_quota(user_id, until)
            task.plan, task.local_date = target, until
            task.position = (
                Task.objects.filter(plan=target, deleted_at__isnull=True).aggregate(m=Max("position"))["m"] or -1
            ) + 1
            task.save()
            services.settle(plan)
            services.settle(target)
        else:
            _finish(plan, task)
        _emit(TASK_SNOOZED, user_id=str(user_id), kind=task.kind, until_days=days)
        return task


def undo_task(user_id, task_id, *, client_id, from_state: str, now: datetime | None = None) -> Task:
    """
    Reverts the last transition within 60 seconds: a tick (manual ticks only: work the student's activity completed is a fact, not
    a click), a skip (back to suggested, the same day only) or an own task's deletion. `from_state` is what the web believes the
    task is in; anything else is `invalid_transition`, a replay is answered with the task as it is.
    """
    now = now or timezone.now()
    with transaction.atomic():
        plan, task = locked(user_id, task_id, include_deleted=True)
        if _replay(task, client_id):
            return task
        if from_state == "deleted":
            if task.deleted_at is None:
                return task  # already restored
            if (now - task.deleted_at).total_seconds() > c.UNDO_WINDOW_SECONDS:
                raise UndoExpiredError
            task.deleted_at = None
            task.last_client_id = client_id
            task.version += 1
            task.save()
            services.settle(plan)
            return task
        if task.deleted_at is not None:
            raise TaskNotFound
        if task.state != from_state:
            raise _invalid(task, "undo")
        within = states.undo_window_open(task.state_changed_at, now)
        if from_state == "done":
            if task.completed_via != "manual":
                raise InvalidTransitionError(
                    "Work you did elsewhere in the app counts, so this tick cannot be undone.",
                    extra={"state": task.state, "action": "undo", "allowed": []},
                )
            try:
                new = states.transition("done", "undo", prev_state=task.prev_state, within_undo=within)
            except states.UndoExpired as error:
                raise UndoExpiredError from error
            except states.InvalidTransition as error:
                raise _invalid(task, "undo", error) from error
        elif from_state == "skipped":
            if task.skip_reason == "swapped":
                raise _invalid(task, "undo")
            if not within:
                raise UndoExpiredError
            today, _tz = generation.student_today(user_id, now)
            try:
                new = states.transition("skipped", "restore", origin=task.origin, same_day=plan.local_date == today)
            except states.InvalidTransition as error:
                raise _invalid(task, "undo", error) from error
        else:
            raise _invalid(task, "undo")
        _enter(task, new, now, client_id)
        _finish(plan, task)
        return task


# ---- swap -------------------------------------------------------------------------------------------------------------------


def swap_task(user_id, task_id, *, client_id, client_ts=None, now: datetime | None = None) -> SwapResult:
    """
    Replaces a suggestion with another unit of work of the same group (else any), chosen by the same composition that built the
    plan, without the keys already in the plan. The old task is `skipped` with reason `swapped`. 20 a day.
    """
    now = now or timezone.now()
    with transaction.atomic():
        again = Task.objects.filter(user_id=user_id, client_id=client_id).first() if client_id else None
        if again is not None and again.swapped_from_id == task_id:
            old = Task.objects.get(pk=task_id, user_id=user_id)
            return SwapResult(old, again)  # a retry of a swap that went through
        plan, task = locked(user_id, task_id)
        if task.origin != "provider":
            raise _invalid(task, "swap")
        if task.state == "skipped" and task.skip_reason == "swapped":
            new = Task.objects.filter(user_id=user_id, swapped_from_id=task.id).first()
            if new is not None:
                return SwapResult(task, new)
        _check_order(task, "swap", now, client_ts)
        try:
            new_state = states.transition(task.state, "swap", prev_state=task.prev_state, origin=task.origin)
        except states.InvalidTransition as error:
            raise _invalid(task, "swap", error) from error
        used = Task.objects.filter(user_id=user_id, local_date=plan.local_date, swapped_from_id__isnull=False).count()
        if used >= c.SWAPS_PER_DAY:
            raise QuotaExceeded(
                "You have swapped as much as you can today.",
                extra={"kind": "swaps", "used": used, "limit": c.SWAPS_PER_DAY},
            )
        today, tz = generation.student_today(user_id, now)
        gen = generation.generate(user_id, plan.local_date, tz, plan=plan)
        group_of = {k.name: k.group for spec in registry.providers() for k in spec.kinds}
        same = [p for p in gen.selection.picks if group_of.get(p.candidate.kind) == group_of.get(task.kind)]
        pick = next(iter(same or gen.selection.picks), None)
        if pick is None or pick.candidate.dedupe_key not in gen.candidates_by_key:
            _emit(TASK_SWAPPED, user_id=str(user_id), kind=task.kind, result="no_alternative")
            raise NoAlternative
        row = services._task_rows(plan, gen, picks=[pick], offset=0)[0]
        row.position = task.position
        row.swapped_from_id = task.id
        row.client_id = client_id
        row.state_changed_at = now
        _enter(task, new_state, now, client_id)
        task.skip_reason = "swapped"
        task.save()
        row.save()
        services.settle(plan)
        _emit(TASK_SWAPPED, user_id=str(user_id), kind=task.kind, result="replaced")
        return SwapResult(task, row)


# ---- the student's own tasks ------------------------------------------------------------------------------------------------


def _plan_for_write(user_id, day: date, tz: str) -> DayPlan:
    """The plan of a day, locked; a day with none gets a `draft` that only holds the student's own tasks until `open/` generates."""
    services._lock(user_id, day)
    plan = DayPlan.objects.select_for_update().filter(user_id=user_id, local_date=day).first()
    if plan is not None:
        return plan
    return DayPlan.objects.create(user_id=user_id, local_date=day, tz=tz, status="draft", generation_no=0)


def _check_day_quota(user_id, day: date) -> None:
    used = Task.objects.filter(user_id=user_id, local_date=day, origin="user", deleted_at__isnull=True).count()
    if used >= c.OWN_TASKS_PER_DAY:
        raise QuotaExceeded(
            f"You can add {c.OWN_TASKS_PER_DAY} tasks a day.",
            extra={"kind": "own_tasks_per_day", "used": used, "limit": c.OWN_TASKS_PER_DAY},
        )


def _check_future_quota(user_id, today: date) -> None:
    used = Task.objects.filter(
        user_id=user_id,
        origin="user",
        local_date__gt=today,
        deleted_at__isnull=True,
        state__in=(*c.OPEN_STATES, "snoozed"),
    ).count()
    if used >= c.OWN_TASKS_OPEN_FUTURE:
        raise QuotaExceeded(
            f"You can have {c.OWN_TASKS_OPEN_FUTURE} open tasks for later days.",
            extra={"kind": "own_tasks_future", "used": used, "limit": c.OWN_TASKS_OPEN_FUTURE},
        )


def _scope(user_id, subject_id, chapter_id, tz: str) -> dict:
    """The subject and chapter columns for an own task, checked against the student's course. Nothing given is fine."""
    if subject_id is None and chapter_id is None:
        return dict(subject_id=None, chapter_id=None, subject_key="", chapter_key="")
    enrollment = coverage_adapter.active_enrollment(user_id)
    if enrollment is None:
        raise InvalidScope("Choose your course first.", extra={"subject_id": ["You have no active course."]})
    papers = {s.subject_id: s for s in coverage_adapter.study_state(user_id, enrollment, tz).subjects}
    chapter = None
    if chapter_id is not None:
        for paper in papers.values():
            chapter = next((ch for ch in paper.chapters if ch.chapter_id == chapter_id), None)
            if chapter is not None:
                if subject_id not in (None, paper.subject_id):
                    raise InvalidScope(extra={"chapter_id": ["This chapter belongs to another paper."]})
                subject_id = paper.subject_id
                break
        if chapter is None:
            raise InvalidScope(extra={"chapter_id": ["This chapter is not in your course."]})
    paper = papers.get(subject_id)
    if paper is None:
        raise InvalidScope(extra={"subject_id": ["This paper is not in your course."]})
    return dict(
        subject_id=paper.subject_id,
        chapter_id=chapter.chapter_id if chapter else None,
        subject_key=paper.key,
        chapter_key=chapter.key if chapter else "",
    )


def add_task(
    user_id,
    *,
    client_id,
    title: str,
    local_date: date | None,
    est_minutes: int,
    subject_id=None,
    chapter_id=None,
    now: datetime | None = None,
) -> tuple[Task, bool]:
    """Returns the task and whether it was created (a retry with the same `client_id` returns the original: 200, not 201)."""
    now = now or timezone.now()
    today, tz = generation.student_today(user_id, now)
    day = local_date or today
    if not today <= day <= today + timedelta(days=c.OWN_TASK_MAX_DAYS_AHEAD):
        raise InvalidDate(
            "Pick today or a day within a month.",
            extra={
                "date": [
                    f"Use a date from {today.isoformat()} to {(today + timedelta(days=c.OWN_TASK_MAX_DAYS_AHEAD)).isoformat()}."
                ]
            },
        )
    with transaction.atomic():
        plan = _plan_for_write(
            user_id, day, tz
        )  # the day's lock first: a retry racing the original waits here and then sees it
        existing = Task.objects.filter(user_id=user_id, client_id=client_id).first()
        if existing is not None:
            return existing, False
        scope = _scope(user_id, subject_id, chapter_id, tz)
        _check_day_quota(user_id, day)
        if day > today:
            _check_future_quota(user_id, today)
        position = (Task.objects.filter(plan=plan, deleted_at__isnull=True).aggregate(m=Max("position"))["m"] or -1) + 1
        try:
            with transaction.atomic():
                task = Task.objects.create(
                    user_id=user_id,
                    plan=plan,
                    local_date=day,
                    origin="user",
                    provider="",
                    kind="own_task",
                    slot="custom",
                    dedupe_key=f"own:{client_id}",
                    title=" ".join(title.split()),
                    reason_code="custom",
                    reason=registry.reason_label("custom"),
                    est_minutes=est_minutes,
                    position=position,
                    client_id=client_id,
                    **scope,
                )
        except IntegrityError:  # the same client id on another day's plan: the first write stands
            return Task.objects.get(user_id=user_id, client_id=client_id), False
        services.settle(plan)
        return task, True


def edit_task(user_id, task_id, changes: dict, *, version: int, now: datetime | None = None) -> Task:
    """Own tasks only. `version` is the one the web last saw: another edit or a state change since then is `state_conflict`."""
    now = now or timezone.now()
    with transaction.atomic():
        plan, task = locked(user_id, task_id)
        if task.origin != "user":
            raise ProviderTaskReadOnly
        if task.version != version:
            raise _conflict(task)
        if "title" in changes:
            task.title = " ".join(changes["title"].split())
        if "est_minutes" in changes:
            task.est_minutes = changes["est_minutes"]
        if changes.get("keep"):
            task.carry_count = 0
        if "subject_id" in changes or "chapter_id" in changes:
            wanted_subject = changes.get("subject_id", task.subject_id if "chapter_id" not in changes else None)
            wanted_chapter = changes.get("chapter_id", task.chapter_id if "subject_id" not in changes else None)
            scope = _scope(user_id, wanted_subject, wanted_chapter, plan.tz)
            for name, value in scope.items():
                setattr(task, name, value)
        new_day = changes.get("date")
        task.version += 1
        if new_day is not None and new_day != task.local_date:
            if task.state not in (*c.OPEN_STATES, "snoozed"):
                raise _invalid(task, "move")
            today, _tz = generation.student_today(user_id, now)
            if not today <= new_day <= today + timedelta(days=c.OWN_TASK_MAX_DAYS_AHEAD):
                raise InvalidDate("Pick today or a day within a month.", extra={"date": ["Out of range."]})
            target = _plan_for_write(user_id, new_day, plan.tz)
            _check_day_quota(user_id, new_day)
            task.plan, task.local_date = target, new_day
            task.position = (
                Task.objects.filter(plan=target, deleted_at__isnull=True).aggregate(m=Max("position"))["m"] or -1
            ) + 1
            if task.state == "snoozed":
                task.snoozed_until = new_day
            task.save()
            services.settle(plan)
            services.settle(target)
        else:
            task.save()
            services.settle(plan)
        return task


def delete_task(user_id, task_id, *, client_id=None, now: datetime | None = None) -> DeleteResult:
    """Soft delete of an own task. The answer says until when `undo` (from_state `deleted`) can bring it back."""
    now = now or timezone.now()
    with transaction.atomic():
        plan, task = locked(user_id, task_id, include_deleted=True)
        if task.origin != "user":
            raise ProviderTaskReadOnly
        if task.deleted_at is None:
            task.deleted_at = now
            task.last_client_id = client_id
            task.version += 1
            task.save()
            services.settle(plan)
        return DeleteResult(task, task.deleted_at + timedelta(seconds=c.UNDO_WINDOW_SECONDS))


# ---- regenerate -------------------------------------------------------------------------------------------------------------


def _fit(picks, kept_minutes: int, budget: int):
    """
    The new picks that fit beside what stays: nothing is added once the plan reaches the fill target, and nothing that would pass
    the hard cap. The composer built its list for an empty day, so without this a regeneration would double a plan.
    """
    out, total = [], kept_minutes
    for pick in picks:
        if total >= budget * c.FILL_TARGET_PCT / 100:
            break
        if total + pick.candidate.est_minutes > budget * c.HARD_CAP_PCT / 100:
            continue
        out.append(pick)
        total += pick.candidate.est_minutes
    return out


def regenerate(
    user_id, *, expected_generation: int, reason: str, client_id, now: datetime | None = None
) -> tuple[DayPlan, dict]:
    """
    Rebuilds today's suggestions. Kept: done, started, snoozed, skipped (a skipped key is never offered twice in a day), the
    student's own and pinned tasks. Replaced: suggested provider tasks (`expired`, `end_reason` regenerated). Optimistic: a stale
    `expected_generation` is 409 `plan_changed`; at most 6 a day. A retry with the same `client_id` returns the plan as it is.
    """
    now = now or timezone.now()
    today, tz = generation.student_today(user_id, now)
    with transaction.atomic():
        services._lock(user_id, today)
        plan = DayPlan.objects.select_for_update().filter(user_id=user_id, local_date=today).first()
        if plan is None or plan.status == "draft":
            raise PlanNotGenerated
        marker = (plan.selection_log or {}).get("regenerate") or {}
        if marker.get("client_id") == str(client_id):
            return plan, {"kept": marker.get("kept", 0), "replaced": marker.get("replaced", 0), "replayed": True}
        if plan.generation_no != expected_generation:
            raise PlanChanged(extra={"generation_no": plan.generation_no})
        used = plan.generation_no - 1
        if used >= c.REGENERATIONS_PER_DAY:
            raise QuotaExceeded(
                "Your plan was rebuilt as often as it can be today.",
                extra={"kind": "regenerations", "used": used, "limit": c.REGENERATIONS_PER_DAY},
            )
        replaceable = Task.objects.filter(
            plan=plan, origin="provider", state="suggested", is_pinned=False, deleted_at__isnull=True
        )
        replaced = replaceable.update(
            prev_state="suggested",
            state="expired",
            end_reason="regenerated",
            state_changed_at=now,
            version=F("version") + 1,
        )
        live = Task.objects.filter(plan=plan, deleted_at__isnull=True).exclude(state="expired")
        kept = live.count()
        kept_minutes = sum(m for m, counts in live.values_list("est_minutes", "counts_toward_day") if counts)
        gen = generation.generate(user_id, today, tz, plan=plan)
        offset = (live.aggregate(m=Max("position"))["m"] if kept else -1) + 1
        picks = _fit(gen.selection.picks, kept_minutes, gen.ctx.budget_minutes) if gen.ctx.enrollment else []
        fields = services.plan_fields(gen, now)
        for name, value in fields.items():
            setattr(plan, name, value)
        marker = {"client_id": str(client_id), "reason": reason, "kept": kept, "replaced": replaced}
        plan.selection_log = {**dict(plan.selection_log), "regenerate": marker}
        plan.generation_no += 1
        plan.save()
        Task.objects.bulk_create(services._task_rows(plan, gen, picks=picks, offset=offset))
        services.settle(plan)
        _emit(PLAN_REGENERATED, user_id=str(user_id), reason=reason, kept_count=kept, replaced_count=replaced)
        return plan, {"kept": kept, "replaced": replaced, "replayed": False}
