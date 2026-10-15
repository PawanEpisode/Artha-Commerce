"""
Writes for day feedback, the adaptive budget and the bonus round (PRD slice 18, FR-F13-36 and FR-F13-37).

- `record_feedback`: one answer per day plan (today's or yesterday's: "after the day closes"); a second answer replaces the first.
- `current_suggestion` / `answer_suggestion`: three unused answers in a row of "too much" or "too little" suggest new daily minutes
  (`domain/adapt.py`). Nothing changes until the student answers with one tap; accepting writes the Today setting `minutes_per_day`,
  and either answer marks those answers used so they never suggest twice.
- `add_bonus`: on a completed day, "Do a little more" adds up to 3 extra tasks within 20 minutes that never count toward completion,
  the ring or the streak (`counts_toward_day` false). Once a day.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core import events
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from . import generation, selectors, services
from .domain import adapt
from .domain import constants as c
from .domain.week import day_completed
from .errors import BonusNotAvailable, InvalidDate, NoBudgetSuggestion, PlanNotGenerated
from .models import DayFeedback, DayPlan, Task

BUDGET_ADAPTED = "today_budget_adapted"
BONUS_ADDED = "today_bonus_added"


@dataclass(frozen=True)
class FeedbackResult:
    feedback: DayFeedback
    suggestion: dict | None


def _current_minutes(user_id) -> int:
    """What the suggestion starts from: the student's own setting, else the budget of their latest plan."""
    setting = selectors.get_settings(user_id).minutes_per_day
    if setting is not None:
        return setting
    latest = DayPlan.objects.filter(user_id=user_id, status__in=("ready", "closed")).order_by("-local_date").first()
    return latest.budget_minutes if latest else c.DEFAULT_BUDGET_MINUTES


def current_suggestion(user_id) -> dict | None:
    ratings = list(
        DayFeedback.objects.filter(user_id=user_id, consumed=False)
        .order_by("-local_date")
        .values_list("rating", flat=True)[: c.FEEDBACK_STREAK]
    )
    return adapt.suggestion(ratings, _current_minutes(user_id))


def record_feedback(user_id, rating: str, *, day=None, now: datetime | None = None) -> FeedbackResult:
    now = now or timezone.now()
    today, _tz = generation.student_today(user_id, now)
    day = day or today
    if day not in (today, today - timedelta(days=1)):
        raise InvalidDate(
            "Answer for today or yesterday.",
            extra={"date": [f"Use {(today - timedelta(days=1)).isoformat()} or {today.isoformat()}."]},
        )
    with transaction.atomic():
        services._lock(user_id, day)
        plan = DayPlan.objects.select_for_update().filter(user_id=user_id, local_date=day).first()
        if plan is None or plan.status == "draft":
            raise PlanNotGenerated
        row, created = DayFeedback.objects.get_or_create(
            plan=plan, defaults={"user_id": user_id, "local_date": day, "rating": rating}
        )
        if not created and row.rating != rating:
            row.rating, row.consumed = rating, False
            row.save(update_fields=["rating", "consumed", "updated_at"])
    return FeedbackResult(row, current_suggestion(user_id))


def answer_suggestion(user_id, *, accept: bool) -> dict:
    """Applies (`accept`) or dismisses the current suggestion. Returns it with `accepted`. 409 `no_budget_suggestion` when none stands."""
    with transaction.atomic():
        services._lock(user_id, c.FEEDBACK_LOCK_DAY)
        suggestion = current_suggestion(user_id)
        if suggestion is None:
            raise NoBudgetSuggestion
        ids = list(
            DayFeedback.objects.filter(user_id=user_id, consumed=False)
            .order_by("-local_date")
            .values_list("pk", flat=True)[: c.FEEDBACK_STREAK]
        )
        DayFeedback.objects.filter(pk__in=ids).update(consumed=True)
        if accept:
            services.save_settings(user_id, {"minutes_per_day": suggestion["minutes"]})
        transaction.on_commit(
            lambda: events.emit(
                BUDGET_ADAPTED, user_id=str(user_id), direction=suggestion["direction"], accepted=accept
            )
        )
    return {**suggestion, "accepted": accept}


# ---- bonus round ------------------------------------------------------------------------------------------------------------


def add_bonus(user_id, *, now: datetime | None = None) -> tuple[DayPlan, int]:
    """Adds the bonus tasks to today's completed plan and returns it with how many were added."""
    now = now or timezone.now()
    today, tz = generation.student_today(user_id, now)
    with transaction.atomic():
        services._lock(user_id, today)
        plan = DayPlan.objects.select_for_update().filter(user_id=user_id, local_date=today).first()
        if plan is None or plan.status == "draft":
            raise PlanNotGenerated
        if (plan.selection_log or {}).get("bonus"):
            raise BonusNotAvailable(extra={"reason": "already_used"})
        if not (
            plan.planned_count > 0
            and day_completed(open_count=plan.open_count, done_count=plan.done_count, skipped_count=plan.skipped_count)
        ):
            raise BonusNotAvailable(extra={"reason": "day_not_complete"})
        gen = generation.generate(user_id, today, tz, plan=plan)
        chosen, minutes = [], 0
        for pick in gen.selection.picks:  # best first; already excludes what the plan holds
            if len(chosen) == c.BONUS_MAX_TASKS:
                break
            if pick.candidate.est_minutes + minutes <= c.BONUS_MAX_MINUTES:
                chosen.append(pick)
                minutes += pick.candidate.est_minutes
        if not chosen:
            raise BonusNotAvailable(extra={"reason": "nothing_to_offer"})
        offset = (Task.objects.filter(plan=plan, deleted_at__isnull=True).aggregate(m=Max("position"))["m"] or 0) + 1
        rows = services._task_rows(plan, gen, picks=chosen, offset=offset)
        for row in rows:
            row.counts_toward_day = False
        Task.objects.bulk_create(rows)
        plan.selection_log = {**dict(plan.selection_log), "bonus": {"count": len(rows), "minutes": minutes}}
        plan.save(update_fields=["selection_log"])
        services.settle(plan)
        transaction.on_commit(
            lambda: events.emit(BONUS_ADDED, user_id=str(user_id), task_count=len(rows), minutes=minutes)
        )
    return plan, len(rows)
