"""Plan limits and what the student has used (PRD 8.5), for the settings screen and the quota sheets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from ..domain.quota import month_start, resets_on
from ..models import MonthlyUsage, QuotaUsage
from ..services import quota


@dataclass(frozen=True)
class UsageView:
    plan: str
    limits: dict[str, int]
    used: dict[str, int]
    resets_on: date


def usage(user_id) -> UsageView:
    now = timezone.now()
    lifetime = QuotaUsage.objects.filter(pk=user_id).first()
    month = MonthlyUsage.objects.filter(user_id=user_id, month=month_start(now)).first()
    used = {
        "storage_bytes": lifetime.bytes_used if lifetime else 0,
        "documents": lifetime.docs_active if lifetime else 0,
        "notes": lifetime.notes_active if lifetime else 0,
        "tags": lifetime.tags_count if lifetime else 0,
        "share_links": lifetime.share_links_active if lifetime else 0,
        "ocr_pages": month.ocr_pages if month else 0,
        "ai_ocr_pages": month.ai_ocr_pages if month else 0,
        "ai_summaries": month.ai_summaries if month else 0,
        "exports": month.exports if month else 0,
        "uploads": month.uploads if month else 0,
    }
    return UsageView(quota.plan_code_for(user_id), quota.limits_for(user_id).as_dict(), used, resets_on(now))
