"""
Subscribers for the Practice Engine.

Listens to domain events such as `practice_session_completed` and idempotently
notifies other modules (Coverage, Tracking) without circular dependencies.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from core import events as core_events

logger = logging.getLogger(__name__)

PRACTICE_COVERAGE_NAMESPACE = uuid.UUID("7b1f3c2a-8d4e-4f5a-9b1c-3e5f7a9b1c3d")
PRACTICE_TRACKING_NAMESPACE = uuid.UUID("8c2e4d3b-9e5f-4a6b-ac2d-4f6a8b0c2d4e")


def on_practice_session_completed(
    *,
    payload: dict[str, Any] | None = None,
    user_id: Any | None = None,
    **kwargs: Any,
) -> None:
    """
    Handles `practice_session_completed` event.
    Forwards chapter completions to Coverage (practice_done, mock_done, revision_done)
    and logs auto-time to Tracking if active_seconds >= 60.
    """
    data = payload or kwargs
    uid = user_id or data.get("user_id")
    if not uid:
        return

    session_id = data.get("session_id")
    mode = data.get("mode", "untimed")
    by_chapter = data.get("by_chapter", [])

    # 1. Forward to Coverage
    try:
        from modules.coverage import services as coverage_services
        from modules.coverage.models import CoverageEvent

        if mode == "revision":
            event_type = CoverageEvent.Type.REVISION_DONE
        elif mode == "exam":
            event_type = CoverageEvent.Type.MOCK_DONE
        else:
            event_type = CoverageEvent.Type.PRACTICE_DONE

        for ch in by_chapter:
            ch_id = ch.get("chapter_id")
            answered = ch.get("answered", 0)
            if not ch_id or answered < 1:
                continue

            # Deterministic client_id for idempotency
            cid = uuid.uuid5(PRACTICE_COVERAGE_NAMESPACE, f"{session_id}:{ch_id}")
            marks = int(ch.get("marks", 0))

            coverage_services.record_event(
                user_id=uid,
                chapter_id=uuid.UUID(ch_id) if isinstance(ch_id, str) else ch_id,
                type=event_type,
                value=marks,
                source=CoverageEvent.Source.QUESTION_BANK,
                client_id=cid,
                strict=False,
            )
    except Exception:
        logger.exception("Failed to forward practice_session_completed to coverage for session %s", session_id)

    # 2. Forward to Tracking (Auto-time capture)
    active_seconds = data.get("active_seconds", 0)
    if active_seconds >= 60:
        try:
            from django.utils import timezone

            from modules.tracking import services as tracking_services
            from modules.tracking.models import ActivityType

            tracker_cid = uuid.uuid5(PRACTICE_TRACKING_NAMESPACE, str(session_id))
            primary_chapter = None
            if by_chapter:
                # pick chapter with most answered questions
                sorted_ch = sorted(by_chapter, key=lambda c: c.get("answered", 0), reverse=True)
                if sorted_ch and sorted_ch[0].get("chapter_id"):
                    raw_chid = sorted_ch[0]["chapter_id"]
                    primary_chapter = uuid.UUID(raw_chid) if isinstance(raw_chid, str) else raw_chid

            tracking_services.add_auto_session(
                user_id=uid,
                client_id=tracker_cid,
                chapter_id=primary_chapter,
                started_at=timezone.now(),
                seconds=active_seconds,
                activity_type=ActivityType.PRACTICE,
            )
        except Exception:
            logger.exception("Failed to forward auto practice session to tracking for session %s", session_id)


def register_subscribers() -> None:
    """Register all Practice event bus subscribers."""
    core_events.subscribe("practice_session_completed", on_practice_session_completed)
