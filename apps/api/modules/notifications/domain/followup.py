"""
When a student who said "Not now" may be asked again (PRD 5.1, W2.5b). Pure rules, so every edge is a unit test.

At most two follow-up asks after the onboarding ask (three asks in all), at least 14 days apart, and only for a student
who chose "Not now" (or closed the browser prompt). A block, an unsupported browser or a missing Home Screen install is
never nagged: Settings explains those. The web shows the ask only right after a finished focus round.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .enums import PermissionState

MAX_ASKS = 3
FOLLOWUP_INTERVAL = timedelta(days=14)

#: Only an undecided-by-choice answer is asked again.
REASKABLE_STATES = frozenset({PermissionState.DISMISSED})


def followup_due(
    state: str,
    ask_count: int,
    last_asked_at: datetime | None,
    decided_at: datetime | None,
    now: datetime,
) -> bool:
    """True when a follow-up ask may be shown now. The clock starts at the later of the last ask and the last answer."""
    if state not in REASKABLE_STATES or ask_count >= MAX_ASKS:
        return False
    since = max((t for t in (last_asked_at, decided_at) if t is not None), default=None)
    return since is None or now - since >= FOLLOWUP_INTERVAL
