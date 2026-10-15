"""
Read-only queries for Today. Every function takes `user_id` and filters on it: another student's rows are never found. Nothing
here writes (`GET plan/` is a read, ERD 0.4), not even the settings row, which is created on the first save.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Count, Max, Q, QuerySet

from .domain import constants as c
from .domain import week
from .models import DayPlan, Task, TodaySettings


def get_plan(user_id, local_date: date) -> DayPlan | None:
    return DayPlan.objects.filter(user_id=user_id, local_date=local_date).first()


def live_tasks(plan: DayPlan) -> QuerySet[Task]:
    """What the plan shows: not deleted, in display order; expired tasks stay hidden except those left over at day end (they read as skipped)."""
    return (
        Task.objects.filter(plan=plan, deleted_at__isnull=True)
        .exclude(Q(state="expired") & ~Q(end_reason="day_ended"))
        .select_related("subject")
        .order_by("position", "created_at")
    )


def get_settings(user_id) -> TodaySettings:
    """The student's row, or an unsaved one with the defaults. Never creates a row."""
    return TodaySettings.objects.filter(pk=user_id).first() or TodaySettings(user_id=user_id)


@dataclass(frozen=True)
class KeyHistory:
    suppressed_keys: frozenset[str]  # skipped too often lately, or snoozed past this date
    miss_counts: dict[str, int]  # dedupe_key -> times it expired unfinished in the last 7 days
    in_plan_keys: frozenset[str]  # a live row exists in today's plan (done, skipped, open): never offered twice


def key_history(user_id, local_date: date, plan: DayPlan | None) -> KeyHistory:
    """The facts about earlier days that the composition needs (PRD 5.4 step 1 and 2). Two queries."""
    skip_since = local_date - timedelta(days=c.SKIP_SUPPRESS_WINDOW_DAYS)
    miss_since = local_date - timedelta(days=c.MISS_WINDOW_DAYS)
    skipped: Counter[str] = Counter()
    missed: Counter[str] = Counter()
    snoozed: set[str] = set()
    rows = (
        Task.objects.filter(user_id=user_id, local_date__gte=min(skip_since, miss_since), local_date__lte=local_date)
        .filter(origin="provider")
        .filter(Q(state="skipped") | Q(state="snoozed") | Q(state="expired", end_reason="day_ended"))
        .values_list("dedupe_key", "state", "local_date", "snoozed_until")
    )
    for key, state, day, until in rows:
        if state == "skipped" and day >= skip_since:
            skipped[key] += 1
        elif state == "snoozed" and until and until > local_date:
            snoozed.add(key)
        elif state == "expired" and day >= miss_since and day < local_date:
            missed[key] += 1
    suppressed = {k for k, n in skipped.items() if n >= c.SKIP_SUPPRESS_COUNT} | snoozed
    in_plan: frozenset[str] = frozenset()
    if plan is not None:
        in_plan = frozenset(
            Task.objects.filter(plan=plan, deleted_at__isnull=True)
            .exclude(state="expired")
            .values_list("dedupe_key", flat=True)
        )
    return KeyHistory(frozenset(suppressed), dict(missed), in_plan)


def done_days(user_id, since: date, until: date) -> set[date]:
    """Local dates in `[since, until]` on which the student completed at least one task."""
    return set(
        Task.objects.filter(user_id=user_id, state="done", local_date__gte=since, local_date__lte=until).values_list(
            "local_date", flat=True
        )
    )


def ever_completed_a_task(user_id) -> bool:
    return Task.objects.filter(user_id=user_id, state="done").exists()


def last_done_by_subject(user_id, since: date) -> dict:
    """subject_id -> the latest local date a task of that paper was completed (a paper the student worked on is not starved)."""
    rows = (
        Task.objects.filter(user_id=user_id, state="done", local_date__gte=since, subject_id__isnull=False)
        .values("subject_id")
        .annotate(latest=Max("local_date"))
    )
    return {r["subject_id"]: r["latest"] for r in rows}


def completion_history(user_id, first: date, last: date, today: date) -> list[dict]:
    """
    One row per local day in `[first, last]` that had a plan, newest first, for the week strip and the history screen. A day without
    a plan is simply absent: the web draws it as "no plan".
    """
    plans = DayPlan.objects.filter(user_id=user_id, local_date__gte=first, local_date__lte=last).order_by("-local_date")
    out = []
    for plan in plans:
        completed = week.day_completed(
            open_count=plan.open_count, done_count=plan.done_count, skipped_count=plan.skipped_count
        )
        out.append(
            {
                "date": plan.local_date,
                "planned_count": plan.planned_count,
                "done_count": plan.done_count,
                "skipped_count": plan.skipped_count,
                "open_count": plan.open_count,
                "planned_minutes": plan.planned_minutes,
                "outcome": week.day_outcome(
                    planned_count=plan.planned_count, done_count=plan.done_count, completed=completed
                ),
                "closed": plan.status == "closed" or plan.local_date < today,
            }
        )
    return out


def week_strip(user_id, today: date) -> list[dict]:
    """The last seven local days ending today, oldest first, every day present (`no_plan` when there was none)."""
    first = today - timedelta(days=6)
    known = {row["date"]: row for row in completion_history(user_id, first, today, today)}
    strip = []
    for n in range(7):
        day = first + timedelta(days=n)
        row = known.get(day)
        strip.append(
            {
                "date": day,
                "outcome": row["outcome"] if row else "no_plan",
                "planned_count": row["planned_count"] if row else 0,
                "done_count": row["done_count"] if row else 0,
            }
        )
    return strip


def own_tasks_on(user_id, day: date) -> QuerySet[Task]:
    """The student's own tasks for a day (including a future day that has only a draft plan)."""
    return (
        Task.objects.filter(user_id=user_id, local_date=day, origin="user", deleted_at__isnull=True)
        .exclude(state="expired")
        .select_related("subject")
        .order_by("position", "created_at")
    )


def provider_task_counts(plan: DayPlan) -> dict[str, int]:
    """Live tasks per provider, for the admin and the contract tests."""
    rows = live_tasks(plan).values("provider").annotate(n=Count("id"))
    return defaultdict(int, {r["provider"]: r["n"] for r in rows})


def reminder_digest(user_id, local_date: date) -> dict:
    """
    What X-01 needs for "3 tasks left, about 20 min" (FR-F13-43): the open count and minutes, the top three titles with their links, and
    `is_done` (true once nothing is open, so reminders stop). A day with no plan has `has_plan: false` and is never "done". Read only.
    """
    plan = get_plan(user_id, local_date)
    if plan is None or plan.status == "draft":
        return {
            "date": local_date.isoformat(),
            "has_plan": False,
            "open_count": 0,
            "open_minutes": 0,
            "top": [],
            "is_done": False,
        }
    open_tasks = list(
        Task.objects.filter(
            plan=plan, state__in=c.OPEN_STATES, deleted_at__isnull=True, counts_toward_day=True
        ).order_by("-is_must_do", "-score", "position")
    )
    return {
        "date": local_date.isoformat(),
        "has_plan": True,
        "open_count": len(open_tasks),
        "open_minutes": sum(t.est_minutes for t in open_tasks),
        "top": [
            {"title": t.title, "link": {"path": t.link_path, "search": dict(t.link_search or {})}}
            for t in open_tasks[:3]
        ],
        "is_done": not open_tasks,
    }
