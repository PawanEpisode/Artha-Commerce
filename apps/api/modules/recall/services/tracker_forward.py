"""
Opt-in time tracking (FR-F15-73): a finished recall session is forwarded to the tracker as ONE auto study session with activity
"revision", under the tracker's own auto-capture rules (switch on, no live timer, no overlap, daily cap). Runs from the
`recall_session_completed` subscriber, once per close; it is idempotent on a client id derived from the session id, so a replayed
event or a second close adds nothing. It never raises: the tracker being unavailable must not fail the close of a session.

The session is tagged with a chapter only when one chapter holds at least half of its reviews (otherwise the time is untagged
revision, which is honest about a mixed session).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from ..adapters import tracking as tracking_adapter

logger = logging.getLogger(__name__)

NAMESPACE = uuid.UUID("5b9a2d4e-7c31-4e08-8f6a-d41c0e93b7a2")
MAIN_CHAPTER_SHARE = 0.5


def client_id_for(session_id) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"recall-session:{session_id}")


def main_chapter(by_chapter: Sequence[dict[str, Any]]) -> str | None:
    """The chapter that holds at least half of the session's reviews, or None. Pure."""
    total = sum(int(c.get("reviews") or 0) for c in by_chapter)
    if not total:
        return None
    top = max(by_chapter, key=lambda c: int(c.get("reviews") or 0))
    if top.get("chapter_id") and int(top["reviews"]) / total >= MAIN_CHAPTER_SHARE:
        return str(top["chapter_id"])
    return None


def forward_session(
    user_id, *, session_id, started_at: str | datetime | None, active_seconds: int, by_chapter: Sequence[dict] = ()
) -> str:
    """Returns the tracker's outcome word, or "skipped" when the event had nothing to forward, or "error" (logged, never raised)."""
    if not started_at or int(active_seconds or 0) <= 0:
        return "skipped"
    when = datetime.fromisoformat(started_at) if isinstance(started_at, str) else started_at
    try:
        _saved, outcome = tracking_adapter.add_revision_session(
            user_id,
            client_id=client_id_for(session_id),
            started_at=when,
            seconds=int(active_seconds),
            chapter_id=main_chapter(by_chapter),
        )
        return outcome
    except Exception:  # noqa: BLE001 - the tracker must never fail the close of a recall session
        logger.warning("Could not forward recall session %s to the tracker", session_id, exc_info=True)
        return "error"
