"""
Domain event subscribers for Performance Analytics (F-10).
Listens to practice events and triggers fact ingestion.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from core import events

from . import services

logger = logging.getLogger(__name__)


def handle_practice_session_completed(**payload: Any) -> None:
    """Triggered when a practice session is submitted or auto-submitted."""
    try:
        user_id_raw = payload.get("user_id")
        session_id_raw = payload.get("session_id") or payload.get("id") or payload.get("payload", {}).get("session_id")

        if not user_id_raw or not session_id_raw:
            return

        user_id = uuid.UUID(str(user_id_raw))
        session_id = uuid.UUID(str(session_id_raw))

        services.refresh_session(user_id, session_id)
    except Exception:
        logger.exception("Failed to handle practice_session_completed in analytics subscriber")


def handle_practice_regraded(**payload: Any) -> None:
    """Triggered when a session is regraded."""
    try:
        user_id_raw = payload.get("user_id")
        session_ids = payload.get("session_ids") or []
        single_id = payload.get("session_id")
        if single_id:
            session_ids.append(single_id)

        if not user_id_raw or not session_ids:
            return

        user_id = uuid.UUID(str(user_id_raw))
        for sid in session_ids:
            services.refresh_session(user_id, uuid.UUID(str(sid)))
    except Exception:
        logger.exception("Failed to handle practice_regraded in analytics subscriber")


def handle_practice_session_deleted(**payload: Any) -> None:
    """Triggered when a practice session is deleted or purged."""
    try:
        user_id_raw = payload.get("user_id")
        session_id_raw = payload.get("session_id") or payload.get("id")

        if not user_id_raw or not session_id_raw:
            return

        user_id = uuid.UUID(str(user_id_raw))
        session_id = uuid.UUID(str(session_id_raw))
        services.forget_session(user_id, session_id)
    except Exception:
        logger.exception("Failed to handle practice_session_deleted in analytics subscriber")


def register_subscribers() -> None:
    """Wires subscribers onto the core synchronous event bus."""
    events.subscribe("practice_session_completed", handle_practice_session_completed)
    events.subscribe("practice_regraded", handle_practice_regraded)
    events.subscribe("practice_session_deleted", handle_practice_session_deleted)
