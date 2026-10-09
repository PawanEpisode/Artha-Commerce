"""The study-day plan (PRD 9.1, ERD Q-2) and the `provide_today` shape F-13 will call. Pure reads: no row is created or changed."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from django.db.models import Min

from ..domain.scheduling import streak
from ..models import RecallCard, RecallDailyRollup
from .forgotten import ForgottenRow, forgotten
from .queue import plan_today
from .study import Study, load_study, recent_seconds_per_review


@dataclass(frozen=True)
class SubjectTile:
    subject_key: str | None
    total: int
    kinds: dict[str, int]


@dataclass(frozen=True)
class TodayPlan:
    study: Study
    mode: str  # normal, catchup, vacation
    new: int
    learning: int
    due: int
    queue_size: int
    deferred: int
    days_to_clear: int
    est_minutes: int
    next_due_at: datetime | None
    tiles: list[SubjectTile]
    forgotten: list[ForgottenRow]
    streak: int
    new_available: int
    catchup_due: int = 0
    oldest_overdue_days: float = 0.0
    exam: None = None  # R2


def _next_due(study: Study) -> datetime | None:
    return RecallCard.objects.filter(
        user_id=study.user_id, status="active", deleted_at__isnull=True, state__gt=0, due_at__gt=study.day_end
    ).aggregate(m=Min("due_at"))["m"]


def today_plan(user_id, *, now: datetime, tz: str | None = None) -> TodayPlan:
    study = load_study(user_id, now, tz)
    queue, rows = plan_today(study)
    kind_of = {i: rows[i][8] for i in queue.ids}
    subject_of = {i: rows[i][1] for i in queue.ids}
    tally: dict[str | None, Counter] = {}
    for i in queue.ids:
        tally.setdefault(subject_of[i], Counter())[kind_of[i]] += 1
    tiles = sorted(
        (SubjectTile(k, sum(c.values()), dict(c)) for k, c in tally.items()),
        key=lambda t: (-t.total, str(t.subject_key)),
    )
    due_reviews = sum(1 for r in rows.values() if r[3] == 2 and r[6] <= study.day_end)
    unseen = RecallCard.objects.filter(user_id=user_id, status="active", deleted_at__isnull=True, state=0).count()
    per_card = recent_seconds_per_review(user_id, study.today)
    mode = "vacation" if study.vacation else ("catchup" if queue.catchup.active else "normal")
    first_from = study.today
    per_day = {
        d.local_date: d.new_cards + d.learn_reviews + d.review_reviews + d.relearn_reviews
        for d in RecallDailyRollup.objects.filter(
            user_id=user_id, local_date__gte=first_from.replace(year=first_from.year - 1)
        )
    }
    return TodayPlan(
        study=study,
        mode=mode,
        new=queue.new,
        learning=queue.learning,
        due=queue.reviews,
        queue_size=len(queue.ids),
        deferred=max(due_reviews - queue.reviews, 0),
        days_to_clear=queue.catchup.days_to_clear,
        est_minutes=math.ceil(len(queue.ids) * per_card / 60) if queue.ids else 0,
        next_due_at=_next_due(study),
        tiles=tiles,
        forgotten=forgotten(user_id, now=now, limit=5),
        streak=streak(per_day, study.today),
        new_available=unseen,
        catchup_due=queue.catchup.due_count,
        oldest_overdue_days=round(queue.catchup.oldest_overdue_days, 1),
    )


# ------------------------------------------------------------------------------- F-13 shape (nothing registers it in R1)
@dataclass(frozen=True)
class RecallTask:
    kind: str  # recall_cards, forgotten_cards, recheck
    title: str
    count: int
    est_minutes: int = 0
    subject_key: str | None = None
    tiles: list[SubjectTile] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderResult:
    key: str
    tasks: list[RecallTask]


def provide_today(user_id, *, now: datetime) -> ProviderResult:
    """What Today (F-13) would show from recall. Local dataclasses: F-13 does not exist yet and nothing is registered."""
    plan = today_plan(user_id, now=now)
    tasks: list[RecallTask] = []
    if plan.queue_size:
        tasks.append(
            RecallTask(
                "recall_cards",
                f"Recall: {plan.queue_size} cards due",
                plan.queue_size,
                plan.est_minutes,
                tiles=plan.tiles,
            )
        )
    if plan.forgotten:
        tasks.append(RecallTask("forgotten_cards", "Forgotten: top 5", len(plan.forgotten)))
    rechecks = RecallCard.objects.filter(user_id=user_id, status="active", needs_recheck=True).count()
    if rechecks:
        tasks.append(RecallTask("recheck", "Re-check after amendment", rechecks))
    return ProviderResult("recall", tasks)
