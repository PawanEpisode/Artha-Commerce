"""
Tracker adapter (F-01.2). The only recall file that imports `modules.tracking`, and only its public `add_auto_session` service
(it holds the opt-in auto-capture rules, so recall does not copy them and imports none of the tracker's models).
"""

from __future__ import annotations

from datetime import datetime

from modules.tracking import services as tracking


def add_revision_session(
    user_id, *, client_id, started_at: datetime, seconds: int, chapter_id=None
) -> tuple[bool, str]:
    """
    Forward one finished recall session as an auto study session with activity "revision". Returns `(saved, outcome)`; the
    outcome is the tracker's own word: "saved", "too_short", "timer_running", "overlap", "daily_cap" or "auto_capture_off".
    Idempotent on `client_id`. Coverage is not told (`add_auto_session` never forwards auto time).
    """
    session, outcome = tracking.add_auto_session(
        user_id,
        client_id=client_id,
        started_at=started_at,
        seconds=seconds,
        activity_type="revision",
        chapter_id=chapter_id,
    )
    return session is not None, outcome
