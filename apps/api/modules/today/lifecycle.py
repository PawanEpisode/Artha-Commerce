"""
What runs on a clock (PRD slice 15, ERD 3.6), called by the cron tick and safe to repeat or overlap:

- `pregenerate`: tomorrow-morning's plan for students who used Today in the last week, made once their own day has begun, so the
  first open is a read. A plan made here is not "opened" (`first_opened_at` stays empty until the student opens it).
- `close_sweep`: a day ends 3 hours after local midnight (the late-night grace of PRD 5.7). Open provider tasks expire with
  `end_reason=day_ended`, the student's own open tasks move to the next day (`carry_count` + 1; one that was already carried
  `OWN_CARRY_MAX` times expires instead, after the student had the "Still relevant?" prompt for a day), the plan closes and
  `today_day_closed` is announced once.
- `prune`: evidence older than 90 days and tasks older than 13 months go; plan counters stay for 24 months (PRD section 8).
- `replan_sweep`: the planner's own clock (R2): re-plans a plan when 2 days were missed or on Monday, and refreshes its health every day.
- `reminder_digest` lives in `selectors`; it only reads.

Every step is bounded by a time budget, so a big backlog is worked off over several ticks.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from core import events
from core.feature_flags import flag_enabled

from . import actions, generation, planner_services, selectors, services
from .domain import constants as c
from .errors import PlannerNotReady
from .models import DayPlan, ReplanEvent, StudyPlan, Task, TaskEvidence
from .planner import constants as pc

logger = logging.getLogger(__name__)

DAY_CLOSED = "today_day_closed"
FLAG = "today_plan"
PLANNER_FLAG = "today_planner"
PLANNER_CHECK_HOURS = 12  # a plan is looked at again this long after its last health check
PLANNER_BATCH = 200
ACTIVE_DAYS = 7  # pre-generate for students whose plan was opened in the last week
CLOSE_BATCH = 200
EVIDENCE_DAYS = 90
TASK_MONTHS = 13
PLAN_MONTHS = 24
PRUNE_BATCH = 2000
TICK_BUDGET_SECONDS = 20.0
MAX_UTC_OFFSET_HOURS = 14


# ---- pre-generation ---------------------------------------------------------------------------------------------------------


def pregenerate(now: datetime | None = None, *, budget_seconds: float = TICK_BUDGET_SECONDS) -> dict[str, int]:
    """Plans for students who opened Today in the last week and have none for their own today yet."""
    now = now or timezone.now()
    deadline = time.monotonic() + budget_seconds
    horizon = (now + timedelta(hours=MAX_UTC_OFFSET_HOURS)).date()  # no student's day is further on than this
    recent = (now - timedelta(days=ACTIVE_DAYS + 1)).date()
    latest = (
        DayPlan.objects.filter(status__in=("ready", "closed"), first_opened_at__isnull=False, local_date__gte=recent)
        .values("user_id")
        .annotate(last=Max("local_date"))
        .filter(last__lt=horizon)
        .order_by("last", "user_id")
    )
    made = skipped = failed = checked = 0
    for row in latest.iterator(chunk_size=200):
        if time.monotonic() >= deadline:
            break
        checked += 1
        user_id = row["user_id"]
        try:
            today, _tz = generation.student_today(user_id, now)
            existing = selectors.get_plan(user_id, today)
            if row["last"] >= today or (existing is not None and existing.status != "draft"):
                continue  # a draft only holds carried or future own tasks: the real plan still has to be made
            if not flag_enabled(FLAG, str(user_id), strict=True):
                skipped += 1
                continue
            result = services.open_today(user_id, now=now, trigger="cron")
            made += 1 if result.created else 0
        except Exception:  # noqa: BLE001 - one student's failure never stops the rest
            logger.exception("today: pre-generation failed for one student")
            failed += 1
    return {"checked": checked, "pregenerated": made, "flag_off": skipped, "failed": failed}


# ---- close sweep ------------------------------------------------------------------------------------------------------------


def _grace_over(plan: DayPlan, now: datetime) -> bool:
    """True once the plan's day has been over for `GRACE_MINUTES` in the plan's own time zone."""
    try:
        zone = ZoneInfo(plan.tz)
    except Exception:  # noqa: BLE001 - an unknown zone name: close on UTC time rather than never
        zone = ZoneInfo("UTC")
    ends = datetime.combine(plan.local_date + timedelta(days=1), datetime.min.time(), tzinfo=zone) + timedelta(
        minutes=c.GRACE_MINUTES
    )
    return now >= ends


def close_plan(plan_id, *, now: datetime | None = None) -> dict | None:
    """Closes one plan; returns its day summary, or None when it was already closed (a second tick changes nothing)."""
    now = now or timezone.now()
    with transaction.atomic():
        services._lock(*DayPlan.objects.values_list("user_id", "local_date").get(pk=plan_id))
        plan = DayPlan.objects.select_for_update().get(pk=plan_id)
        if plan.closed_at is not None or plan.status == "closed":
            return None
        was_draft = plan.status == "draft"
        planned = plan.planned_count
        expired = carried = 0
        open_tasks = list(
            Task.objects.select_for_update()
            .filter(plan=plan, state__in=c.OPEN_STATES, deleted_at__isnull=True)
            .order_by("position", "created_at")
        )
        for task in open_tasks:
            if task.origin == "user" and task.carry_count < c.OWN_CARRY_MAX:
                _carry(task, plan, now)
                carried += 1
            else:
                actions._enter(task, "expired", now, None)
                task.end_reason = "day_ended"
                task.save()
                expired += 1
        if open_tasks:
            services.settle(plan)
        plan.closed_at = now
        if not was_draft:
            plan.status = "closed"
        plan.save()
        summary = dict(
            user_id=str(plan.user_id),
            date=plan.local_date.isoformat(),
            done=plan.done_count,
            skipped=plan.skipped_count
            - expired,  # what the student skipped; the expired ones are reported on their own
            expired=expired,
            planned=planned,
            completed=_completed(plan),
            comeback=plan.budget_source == "comeback",
        )
        if not was_draft:
            transaction.on_commit(lambda: events.emit(DAY_CLOSED, **summary))
    summary["carried"] = carried
    summary["draft"] = was_draft
    return summary


def _completed(plan: DayPlan) -> bool:
    from .domain.week import day_completed

    return (
        day_completed(open_count=plan.open_count, done_count=plan.done_count, skipped_count=plan.skipped_count)
        and plan.planned_count > 0
    )


def _carry(task: Task, plan: DayPlan, now: datetime) -> None:
    """An own task still open at day end moves, same row, to the next day's plan (a draft when the day has none)."""
    target = actions._plan_for_write(task.user_id, plan.local_date + timedelta(days=1), plan.tz)
    task.plan, task.local_date = target, target.local_date
    task.carry_count += 1
    task.position = (
        Task.objects.filter(plan=target, deleted_at__isnull=True).aggregate(m=Max("position"))["m"] or -1
    ) + 1
    task.version += 1
    task.state_changed_at = now
    task.save()
    services.settle(target)


def close_sweep(now: datetime | None = None, *, budget_seconds: float = TICK_BUDGET_SECONDS) -> dict[str, int]:
    """Closes every plan whose day plus grace is over, oldest first, in batches."""
    now = now or timezone.now()
    deadline = time.monotonic() + budget_seconds
    horizon = (now + timedelta(hours=MAX_UTC_OFFSET_HOURS)).date()
    due = (
        DayPlan.objects.filter(closed_at__isnull=True, local_date__lt=horizon)
        .order_by("local_date", "user_id")
        .values_list("pk", flat=True)[:CLOSE_BATCH]
    )
    closed = expired = carried = 0
    for plan_id in list(due):
        if time.monotonic() >= deadline:
            break
        try:
            plan = DayPlan.objects.get(pk=plan_id)
            if not _grace_over(plan, now):
                continue
            summary = close_plan(plan_id, now=now)
        except Exception:  # noqa: BLE001
            logger.exception("today: closing one plan failed")
            continue
        if summary is not None:
            closed += 1
            expired += summary["expired"]
            carried += summary["carried"]
    return {"closed": closed, "expired": expired, "carried": carried}


# ---- planner ----------------------------------------------------------------------------------------------------------------


def replan_sweep(now: datetime | None = None, *, budget_seconds: float = TICK_BUDGET_SECONDS) -> dict[str, int]:
    """Active plans not checked in the last 12 hours, oldest check first: automatic re-plan or health refresh, only while the flag is on."""
    now = now or timezone.now()
    deadline = time.monotonic() + budget_seconds
    due = (
        StudyPlan.objects.filter(status="active")
        .filter(Q(health_checked_at__isnull=True) | Q(health_checked_at__lt=now - timedelta(hours=PLANNER_CHECK_HOURS)))
        .order_by("health_checked_at", "id")
        .values_list("user_id", flat=True)[:PLANNER_BATCH]
    )
    counts = {"checked": 0, "replanned": 0, "refreshed": 0, "archived": 0, "flag_off": 0, "failed": 0}
    for user_id in list(due):
        if time.monotonic() >= deadline:
            break
        counts["checked"] += 1
        try:
            if not flag_enabled(PLANNER_FLAG, str(user_id), strict=True):
                counts["flag_off"] += 1
                continue
            outcome = planner_services.auto_replan(user_id, now=now)
        except PlannerNotReady:
            continue  # no exam date for now: the plan waits
        except Exception:  # noqa: BLE001 - one student's failure never stops the rest
            logger.exception("today: planner check failed for one student")
            counts["failed"] += 1
            continue
        key = outcome if outcome in ("refreshed", "archived") else "replanned"
        if outcome != "none":
            counts[key] += 1
    return counts


# ---- prune ------------------------------------------------------------------------------------------------------------------


def prune(now: datetime | None = None) -> dict[str, int]:
    now = now or timezone.now()
    evidence_ids = list(
        TaskEvidence.objects.filter(created_at__lt=now - timedelta(days=EVIDENCE_DAYS)).values_list("pk", flat=True)[
            :PRUNE_BATCH
        ]
    )
    evidence = TaskEvidence.objects.filter(pk__in=evidence_ids).delete()[0] if evidence_ids else 0
    task_cut = _months_ago(now.date(), TASK_MONTHS)
    task_ids = list(
        Task.objects.filter(local_date__lt=task_cut).values_list("pk", flat=True)[:PRUNE_BATCH]
    )  # evidence rows go with them (cascade)
    tasks = Task.objects.filter(pk__in=task_ids).delete()[0] if task_ids else 0
    plan_cut = _months_ago(now.date(), PLAN_MONTHS)
    plans = DayPlan.objects.filter(local_date__lt=plan_cut, tasks__isnull=True)
    plan_ids = list(plans.values_list("pk", flat=True)[:PRUNE_BATCH])
    plans_deleted = DayPlan.objects.filter(pk__in=plan_ids).delete()[0] if plan_ids else 0
    event_cut = _months_ago(now.date(), pc.REPLAN_EVENT_MONTHS)
    event_ids = list(
        ReplanEvent.objects.filter(created_at__date__lt=event_cut).values_list("pk", flat=True)[:PRUNE_BATCH]
    )
    replan_events = ReplanEvent.objects.filter(pk__in=event_ids).delete()[0] if event_ids else 0
    return {"evidence": evidence, "tasks": tasks, "plans": plans_deleted, "replan_events": replan_events}


def _months_ago(day: date, months: int) -> date:
    total = day.year * 12 + day.month - 1 - months
    return date(total // 12, total % 12 + 1, 1)


# ---- the tick ---------------------------------------------------------------------------------------------------------------


def tick(now: datetime | None = None) -> dict[str, dict]:
    """One cron call: close first (so a carried task is in tomorrow's plan before it is made), then pre-generate, then the planner, then prune."""
    now = now or timezone.now()
    return {
        "close": close_sweep(now),
        "pregenerate": pregenerate(now),
        "planner": replan_sweep(now),
        "prune": prune(now),
    }
