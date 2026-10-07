"""
Version rows (ERD 2.5, 6.4). Every accepted change writes one row in the same transaction as the note update. Autosaves
coalesce: while the previous version is an autosave updated within `COALESCE_WINDOW`, the next autosave rewrites that row
(it takes the newer `rev`), so a burst of typing is one version. A burst is also closed after `COALESCE_SPAN` so a long
session still leaves history. Why a row per revision, even for a pin or a move: it keeps `body_at(rev)` exact, which the
3-way merge needs as its base.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..models import Note, NoteVersion

COALESCE_WINDOW = timedelta(seconds=60)
COALESCE_SPAN = timedelta(minutes=10)


def record(note: Note, *, source: str, now: datetime) -> NoteVersion:
    """Call after `note.rev` has been bumped to the new revision."""
    previous = NoteVersion.objects.filter(note=note, rev=note.rev - 1).first()
    if (
        source == NoteVersion.Source.AUTOSAVE
        and previous is not None
        and previous.source == NoteVersion.Source.AUTOSAVE
        and now - previous.updated_at <= COALESCE_WINDOW
        and now - previous.created_at <= COALESCE_SPAN
    ):
        previous.rev, previous.title, previous.body_md = note.rev, note.title, note.body_md
        previous.save(update_fields=["rev", "title", "body_md", "updated_at"])
        return previous
    return NoteVersion.objects.create(
        note=note, user_id=note.user_id, rev=note.rev, title=note.title, body_md=note.body_md, source=source
    )


def body_at(note: Note, rev: int) -> str | None:
    """The body as it was at exactly `rev`, or None when that revision was folded into a later autosave."""
    return NoteVersion.objects.filter(note=note, rev=rev).values_list("body_md", flat=True).first()
