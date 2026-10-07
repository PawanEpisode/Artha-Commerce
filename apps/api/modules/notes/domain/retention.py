"""
Version retention (ERD 6.4), pure. Every revision is kept for 24 hours. After that, one autosave per day is kept for 90
days, manual versions (manual, restore, merge, ai) are kept up to a cap of 20 per note, and autosaves older than 90 days go.
The newest version of a note is never removed, whatever its age.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

FULL_HISTORY = timedelta(hours=24)
AUTOSAVE_DAYS = 90
MANUAL_CAP = 20
AUTOSAVE = "autosave"


@dataclass(frozen=True)
class VersionInfo:
    id: object
    rev: int
    source: str
    created_at: datetime


def versions_to_delete(versions: list[VersionInfo], now: datetime) -> list[object]:
    """Ids to remove from one note's history. `versions` may be in any order."""
    if not versions:
        return []
    ordered = sorted(versions, key=lambda v: v.rev, reverse=True)
    newest = ordered[0]
    doomed: set[object] = set()
    manual_seen = 0
    kept_days: set[object] = set()
    for v in ordered:
        age = now - v.created_at
        if v.id == newest.id or age <= FULL_HISTORY:
            if v.source != AUTOSAVE:
                manual_seen += 1
            continue
        if v.source == AUTOSAVE:
            day = v.created_at.date()
            if age > timedelta(days=AUTOSAVE_DAYS) or day in kept_days:
                doomed.add(v.id)
            else:
                kept_days.add(day)
        else:
            manual_seen += 1
            if manual_seen > MANUAL_CAP:
                doomed.add(v.id)
    return [v.id for v in ordered if v.id in doomed]
