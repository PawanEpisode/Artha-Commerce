"""
Is AI allowed to run at all, right now? Everything that costs money or sends a student's text to Google asks here first, in
the request AND again in the worker. All of it fails closed: a missing setting means off.

    GEMINI_API_KEY                  the key (API and worker only)
    GEMINI_DATA_TIER=paid           the owner confirmed the key's Google Cloud project has an active billing account, so
                                    Google's Paid Services data terms apply (not the consumer Gemini or Google AI Pro plan)
    NOTES_AI_CONSENT_APPROVED       the consent version the owner approved; must equal `domain.ai_consent.VERSION`
    NOTES_AI_SUMMARY_ENABLED / NOTES_AI_OCR_ENABLED   kill switches (default on)
    NOTES_AI_DAILY_BUDGET_PAISE     all students together, per India day; 0 keeps AI off
"""

from __future__ import annotations

from datetime import datetime

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from ..domain import ai_consent
from ..domain.quota import IST
from ..errors_ai import AiBudgetExhausted, AiUnavailable
from ..models import AiJob

KINDS = ("summary", "ocr")
# What a running or queued job is assumed to cost until it finishes (ERD 6.1: a capped summary is about 5.5 rupees).
RESERVE_PAISE = {"exam_summary": 600, "ocr_page_ai": 500}


def unavailable_reason(kind: str) -> str | None:
    """`None` when AI of this kind may run, else a short code (never shown to students, used by logs and the admin)."""
    if not settings.GEMINI_API_KEY:
        return "not_configured"
    if settings.GEMINI_DATA_TIER != "paid":
        return "data_tier"
    if settings.NOTES_AI_CONSENT_APPROVED != ai_consent.VERSION:
        return "wording_pending"
    if kind == "summary" and not settings.NOTES_AI_SUMMARY_ENABLED:
        return "disabled"
    if kind == "ocr" and not settings.NOTES_AI_OCR_ENABLED:
        return "disabled"
    if settings.NOTES_AI_DAILY_BUDGET_PAISE <= 0:
        return "no_budget"
    return None


def available(kind: str) -> bool:
    return unavailable_reason(kind) is None


def require(kind: str) -> None:
    if unavailable_reason(kind) is not None:
        raise AiUnavailable


def _day_start(now: datetime) -> datetime:
    local = now.astimezone(IST)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def spent_today_paise(now: datetime | None = None) -> int:
    """Cost of today's jobs (India day) plus a reserve for each one still running. The ledger is `notes_aijob`."""
    now = now or timezone.now()
    since = _day_start(now)
    jobs = AiJob.objects.filter(created_at__gte=since)
    actual = jobs.exclude(status__in=AiJob.ACTIVE).aggregate(total=Sum("cost_paise"))["total"] or 0
    reserved = sum(
        RESERVE_PAISE.get(k, 0) * jobs.filter(status__in=AiJob.ACTIVE, kind=k).count() for k in RESERVE_PAISE
    )
    return actual + reserved


def check_budget(kind_of_job: str, now: datetime | None = None) -> None:
    """
    Refuses a new job when today's shared budget would be passed. A soft cap: two requests at the same instant can both pass
    and overshoot by a few rupees; per-student quotas (the money limit that matters) are exact.
    """
    spent = spent_today_paise(now)
    if spent + RESERVE_PAISE.get(kind_of_job, 0) > settings.NOTES_AI_DAILY_BUDGET_PAISE:
        raise AiBudgetExhausted
