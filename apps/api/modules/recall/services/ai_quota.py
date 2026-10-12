"""
The daily AI quota (PRD 8.3), counted per India day in `recall_aiusage`. A charge is ONE conditional UPDATE, never read then write,
so two requests racing for the last batch cannot both pass. The unused part is refunded when a batch makes fewer cards than it
reserved, and the whole charge when it fails or is cancelled. Cached or repeated requests are never charged.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from core.plans import plan_code_for

from ..errors import QuotaExceeded
from ..models import RecallAiUsage
from . import quota

IST = ZoneInfo("Asia/Kolkata")


def today(now: datetime | None = None) -> date:
    return (now or timezone.now()).astimezone(IST).date()


def resets_on(day: date) -> date:
    return day + timedelta(days=1)


def used(user_id, day: date) -> tuple[int, int]:
    """`(batches, suggestions)` used on `day`."""
    row = RecallAiUsage.objects.filter(user_id=user_id, day=day).values_list("batches", "suggestions").first()
    return row or (0, 0)


def charge(user_id, day: date, suggestions: int) -> None:
    """One batch and `suggestions` cards against today's allowance, or 429 `quota_exceeded` saying which limit and when it resets."""
    limits = quota.limits_for(user_id)
    RecallAiUsage.objects.bulk_create([RecallAiUsage(user_id=user_id, day=day)], ignore_conflicts=True)
    updated = RecallAiUsage.objects.filter(
        user_id=user_id,
        day=day,
        batches__lte=limits.ai_batches_per_day - 1,
        suggestions__lte=limits.ai_suggestions_per_day - suggestions,
    ).update(batches=F("batches") + 1, suggestions=F("suggestions") + suggestions, updated_at=timezone.now())
    if updated:
        return
    batches, cards = used(user_id, day)
    kind = "ai_batches" if batches >= limits.ai_batches_per_day else "ai_suggestions"
    limit = limits.ai_batches_per_day if kind == "ai_batches" else limits.ai_suggestions_per_day
    raise QuotaExceeded(
        extra={
            "kind": kind,
            "used": batches if kind == "ai_batches" else cards,
            "limit": limit,
            "plan": plan_code_for(user_id),
            "resets_on": resets_on(day).isoformat(),
        }
    )


def refund(user_id, day: date | None, *, suggestions: int, batch: bool) -> None:
    """Give back unused cards (and the batch itself when it produced nothing). Clamps at zero; a missing day is a no-op."""
    if day is None or (suggestions <= 0 and not batch):
        return
    RecallAiUsage.objects.filter(user_id=user_id, day=day).update(
        suggestions=Greatest(F("suggestions") - suggestions, Value(0)),
        batches=Greatest(F("batches") - (1 if batch else 0), Value(0)),
        updated_at=timezone.now(),
    )
