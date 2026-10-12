"""
Is AI allowed to run at all, right now? The request AND the worker ask here first; everything fails closed (a missing setting means
off), as in `notes.services.ai_gate`:

    GEMINI_API_KEY                the key (API and worker only)
    GEMINI_DATA_TIER=paid         the owner confirmed Google's Paid Services data terms apply to the key's project
    RECALL_AI_CONSENT_APPROVED    the wording version the owner approved; must equal `domain.ai_consent.VERSION`
    RECALL_AI_ENABLED             kill switch (default on)
    RECALL_AI_DAILY_BUDGET_PAISE  all students together, per India day; 0 keeps AI off
"""

from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from ..domain import ai_consent
from ..domain import suggestions as sdomain
from ..errors import AiUnavailable
from ..models import RecallAiCall, RecallSuggestionBatch
from .ai_quota import IST


def unavailable_reason(user_id=None) -> str | None:
    """`None` when AI may run, else a short code (for logs and the admin, never shown to a student)."""
    if not settings.GEMINI_API_KEY:
        return "not_configured"
    if settings.GEMINI_DATA_TIER != "paid":
        return "data_tier"
    if settings.RECALL_AI_CONSENT_APPROVED != ai_consent.VERSION:
        return "wording_pending"
    if not settings.RECALL_AI_ENABLED:
        return "disabled"
    if settings.RECALL_AI_DAILY_BUDGET_PAISE <= 0:
        return "no_budget"
    return None


def available() -> bool:
    return unavailable_reason() is None


def require() -> None:
    if unavailable_reason() is not None:
        raise AiUnavailable


def spent_today_paise(now: datetime | None = None) -> int:
    """Cost of today's calls (India day) plus a reserve for each batch still queued or running."""
    now = now or timezone.now()
    since = now.astimezone(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    actual = RecallAiCall.objects.filter(created_at__gte=since).aggregate(t=Sum("cost_paise"))["t"] or 0
    active = RecallSuggestionBatch.objects.filter(
        status__in=RecallSuggestionBatch.ACTIVE, created_at__gte=since
    ).count()
    return actual + active * sdomain.RESERVE_PAISE


def check_budget(now: datetime | None = None) -> None:
    """A soft cap: two requests at the same instant can both pass. The per-student quotas are exact."""
    if spent_today_paise(now) + sdomain.RESERVE_PAISE > settings.RECALL_AI_DAILY_BUDGET_PAISE:
        raise AiUnavailable
