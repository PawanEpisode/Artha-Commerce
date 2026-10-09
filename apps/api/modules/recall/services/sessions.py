"""Study sessions (ERD 3.5): open (idempotent on the client id), close (once, emits `recall_session_completed`), idle auto-close."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import events

from ..domain import limits as lim
from ..domain.scheduling import local_date_of, streak
from ..errors import InvalidSetting
from ..models import RecallCard, RecallDailyRollup, RecallReviewLog, RecallSession
from . import student

SOURCES = RecallSession.SOURCES
AUTO_CLOSE_BATCH = 200


def valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


def open_session(
    user_id,
    client_id,
    *,
    source: str,
    spec: dict | None = None,
    tz: str | None = None,
    planned_count: int = 0,
    now: datetime | None = None,
) -> tuple[RecallSession, bool]:
    now = now or timezone.now()
    if source not in SOURCES:
        raise InvalidSetting(
            extra={"errors": [{"field": "source", "code": "bad_source", "message": "Unknown source."}]}
        )
    own_tz, day_start = student.study_clock(user_id)
    tz = tz or own_tz
    if not valid_tz(tz):
        raise InvalidSetting(extra={"errors": [{"field": "tz", "code": "bad_tz", "message": "Unknown time zone."}]})
    with transaction.atomic():
        existing = RecallSession.objects.filter(user_id=user_id, client_id=client_id).first()
        if existing is not None:
            return existing, False
        try:
            with transaction.atomic():
                row = RecallSession.objects.create(
                    user_id=user_id,
                    client_id=client_id,
                    source=source,
                    spec={"v": 1, **(spec or {})},
                    started_at=now,
                    last_event_at=now,
                    tz=tz,
                    local_date=local_date_of(now, tz, day_start),
                    planned_count=max(0, min(int(planned_count), 32000)),
                )
        except IntegrityError:
            return RecallSession.objects.get(user_id=user_id, client_id=client_id), False
        return row, True


def summary(session: RecallSession, user_id, now: datetime) -> dict:
    rows = RecallReviewLog.objects.filter(user_id=user_id, session_id=session.id, kind="review").exclude(
        id__in=RecallReviewLog.objects.filter(user_id=user_id, kind="undo").values("voids_id")
    )
    chapters = dict(RecallCard.objects.filter(user_id=user_id).values_list("id", "chapter_id"))
    by_chapter: dict[str, dict] = {}
    for card_id, rating in rows.values_list("card_id", "rating"):
        key = str(chapters.get(card_id) or "")
        slot = by_chapter.setdefault(key, {"chapter_id": key or None, "reviews": 0, "again": 0})
        slot["reviews"] += 1
        slot["again"] += 1 if rating == 1 else 0
    tz, day_start = student.study_clock(user_id)
    today = local_date_of(now, tz, day_start)
    per_day = {
        d.local_date: d.new_cards + d.learn_reviews + d.review_reviews + d.relearn_reviews
        for d in RecallDailyRollup.objects.filter(user_id=user_id, local_date__gte=today - timedelta(days=120))
    }
    return {
        "session_id": str(session.id),
        "source": session.source,
        "reviewed": session.reviewed,
        "new": session.new_count,
        "ratings": {"again": session.again, "hard": session.hard, "good": session.good, "easy": session.easy},
        "active_seconds": session.active_seconds,
        "by_chapter": sorted(by_chapter.values(), key=lambda c: -c["reviews"]),
        "streak_after": streak(per_day, today),
    }


def close_session(
    user_id, session_id, *, auto: bool = False, now: datetime | None = None
) -> tuple[RecallSession, dict]:
    now = now or timezone.now()
    with transaction.atomic():
        session = RecallSession.objects.select_for_update().filter(user_id=user_id, id=session_id).first()
        if session is None:
            raise NotFound("Session not found.")
        if session.status != "open":
            return session, summary(session, user_id, now)
        session.status = "auto_closed" if auto else "closed"
        session.ended_at = session.last_event_at if auto else now
        session.save(
            update_fields=["status", "ended_at", "updated_at"]
            if hasattr(session, "updated_at")
            else ["status", "ended_at"]
        )
        data = summary(session, user_id, now)
        payload = {"user_id": str(user_id), "auto": auto, "local_date": session.local_date.isoformat(), **data}
        transaction.on_commit(lambda: events.emit("recall_session_completed", **payload))
        return session, data


def close_idle(*, now: datetime | None = None, limit: int = AUTO_CLOSE_BATCH) -> int:
    """The tick: close sessions with no review for 60 minutes. Bounded and safe to repeat."""
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=lim.SESSION_IDLE_CLOSE_MINUTES)
    todo = list(
        RecallSession.objects.filter(status="open", last_event_at__lt=cutoff)
        .order_by("last_event_at")
        .values_list("user_id", "id")[:limit]
    )
    for user_id, session_id in todo:
        close_session(user_id, session_id, auto=True, now=now)
    return len(todo)
