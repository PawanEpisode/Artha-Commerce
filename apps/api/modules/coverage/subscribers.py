"""
Coverage reacts to other modules' events (ERD F-03 3.4, FR-F03-43). Subscribing is the whole contract: coverage never imports
the module that announces, it only knows the event name and payload.

`notes_chapter_counts_changed` becomes one `note_added` ledger event (`source=notes`) carrying the chapter's note and
highlight count and whether an exam summary exists. It is display only: the coverage percentage is unchanged. The ledger key
is derived from the emission's `event_id`, so a replayed delivery writes nothing twice.
"""

from __future__ import annotations

import uuid

from . import services
from .models import CoverageEvent

NOTES_CHAPTER_COUNTS_CHANGED = "notes_chapter_counts_changed"  # name of notes' event, see core/event docs
_NAMESPACE = uuid.UUID("6f1c2a52-3a0e-4b0b-9a53-0d1f6a8e7c11")


def on_notes_chapter_counts_changed(
    *, user_id, event_id, chapter_id, chapter_key, counts, has_summary, **_ignored
) -> None:
    services.record_event(
        user_id,
        chapter_id,
        CoverageEvent.Type.NOTE_ADDED,
        value=int(counts.get("notes", 0)) + int(counts.get("highlights", 0)),
        source=CoverageEvent.Source.NOTES,
        client_id=uuid.uuid5(_NAMESPACE, str(event_id)),
        source_ref=str(chapter_key)[:64],
        payload={
            "notes": int(counts.get("notes", 0)),
            "highlights": int(counts.get("highlights", 0)),
            "has_summary": bool(has_summary),
        },
        strict=False,  # a student not enrolled in that syllabus simply has no coverage row to show it on
    )
