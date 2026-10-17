"""
Adapter for Time Tracking (F-01.2 tracking module).
"""

from __future__ import annotations

import uuid
from datetime import date

from django.db.models import Sum

from modules.tracking import selectors as tracking_selectors
from modules.tracking.models import StudySession


def get_student_tz_and_week_start(user_id: uuid.UUID) -> tuple[str, str]:
    """Returns (tz, week_start) for the student."""
    settings = tracking_selectors.settings_or_default(user_id)
    return getattr(settings, "tz", "Asia/Kolkata"), getattr(settings, "week_start", "mon")


def get_seconds_by_chapter(
    user_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[uuid.UUID, int]:
    """
    Returns aggregated study seconds by chapter_id for the given date range.
    """
    try:
        qs = StudySession.objects.filter(user_id=user_id)
        if start_date:
            qs = qs.filter(study_date__gte=start_date)
        if end_date:
            qs = qs.filter(study_date__lte=end_date)

        rows = qs.values("chapter_id").annotate(total_sec=Sum("focus_seconds"))
        res: dict[uuid.UUID, int] = {}
        for r in rows:
            cid = r.get("chapter_id")
            if cid:
                res[cid] = int(r.get("total_sec") or 0)
        return res
    except Exception:
        return {}

