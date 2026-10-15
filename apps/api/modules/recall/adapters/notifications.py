"""Adapter for dispatching notifications from Recall."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_suggestions_ready(user_id: str, batch_id: str, *, failed: bool = False) -> None:
    try:
        from modules.notifications.services.notify import notify

        notify(
            user_id,
            "recall_suggestions_ready",
            context={"batch_id": batch_id, "failed": failed},
            dedupe_ref={"batch_id": batch_id},
        )
    except Exception:
        logger.exception("Failed to send recall_suggestions_ready notification")
