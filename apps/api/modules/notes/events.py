"""
Domain events announced by notes (ERD 3.4), through `core.events`. Payloads carry ids and counts, never text.

`notes_chapter_counts_changed` is emitted when an item is created, trashed, restored or moved to another chapter, and never
for an edit, so a consumer sees at most one event per real change. It is sent after the transaction commits (a rolled-back
write announces nothing) with the counts as they are then. Payload: `user_id`, `event_id` (unique per emission, what a
consumer derives its idempotency key from), `level_id`, `subject_key`, `chapter_id`, `chapter_key`, `counts`
(`{notes, highlights, marks, documents}`), `has_summary`, `reason` (`created`, `trashed`, `restored`, `relinked`).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from django.db import transaction

from core import events as bus

NOTES_CHAPTER_COUNTS_CHANGED = "notes_chapter_counts_changed"

# (level_id, subject_key, chapter_key, chapter_id) as returned by `Note.link_key()`
LinkKey = tuple


def announce_counts(user_id, keys: Iterable[LinkKey | None], reason: str) -> None:
    """Announce the counts of every distinct chapter in `keys` once the surrounding transaction has committed."""
    distinct = {k[:3]: k for k in keys if k}
    if not distinct:
        return
    transaction.on_commit(lambda: _emit_all(user_id, list(distinct.values()), reason))


def _emit_all(user_id, keys: list[LinkKey], reason: str) -> None:
    from . import selectors  # local: selectors import models, events is imported by services at module load

    for level_id, subject_key, chapter_key, chapter_id in keys:
        counts = selectors.chapter_counts(user_id, level_id, subject_key, chapter_key)
        bus.emit(
            NOTES_CHAPTER_COUNTS_CHANGED,
            user_id=str(user_id),
            event_id=str(uuid.uuid4()),
            level_id=str(level_id),
            subject_key=subject_key,
            chapter_id=str(chapter_id),
            chapter_key=chapter_key,
            counts={
                "notes": counts.notes,
                "highlights": counts.highlights,
                "marks": counts.marks,
                "documents": counts.documents,
            },
            has_summary=counts.has_summary,
            reason=reason,
        )
