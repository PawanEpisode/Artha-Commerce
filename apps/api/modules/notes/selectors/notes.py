"""Reads of single notes and note lists: detail, filtered list, trash, recent, versions and the offline changes feed."""

from __future__ import annotations

from typing import Any

from django.db.models import Q

from ..models import Note, NoteVersion
from ._common import (
    NoteCard,
    NoteFilter,
    Page,
    apply_filter,
    cards,
    clamp_limit,
    decode_cursor,
    encode_cursor,
    keyset_after,
    live_notes,
    parse_ts,
)
from .search import text_filter

VERSION_LIST_LIMIT = 200


def get_note(user_id, note_id) -> NoteCard | None:
    """The student's note, trashed or not; None for anyone else's (the view answers 404)."""
    note = Note.objects.filter(pk=note_id, user_id=user_id).first()
    return cards([note])[0] if note else None


def list_notes(user_id, flt: NoteFilter, *, cursor: str | None = None, limit: int | None = None) -> Page[NoteCard]:
    """Live notes, newest change first. Cursor is keyset on `(updated_at desc, id)`."""
    limit = clamp_limit(limit)
    qs = text_filter(apply_filter(live_notes(user_id), flt), flt.q)
    qs = keyset_after(qs, ts_field="updated_at", rank=0, cursor=decode_cursor(cursor)).order_by("-updated_at", "id")
    return _page(qs, limit, ts_attr="updated_at")


def list_trash(user_id, *, cursor: str | None = None, limit: int | None = None) -> Page[NoteCard]:
    """Trashed notes, most recently trashed first (they purge 30 days after `deleted_at`)."""
    limit = clamp_limit(limit)
    qs = Note.objects.filter(user_id=user_id, deleted_at__isnull=False)
    qs = keyset_after(qs, ts_field="deleted_at", rank=0, cursor=decode_cursor(cursor)).order_by("-deleted_at", "id")
    return _page(qs, limit, ts_attr="deleted_at")


def _page(qs, limit: int, *, ts_attr: str) -> Page[NoteCard]:
    rows = list(qs[: limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    token = encode_cursor([getattr(rows[-1], ts_attr), 0, rows[-1].id]) if more else None
    return Page(cards(rows), token)


def recent(user_id, *, limit: int = 10) -> list[NoteCard]:
    """The latest changed notes (hub, Today)."""
    return cards(list(live_notes(user_id).order_by("-updated_at", "id")[: clamp_limit(limit, 10)]))


def list_versions(user_id, note_id) -> list[NoteVersion] | None:
    """Newest first, at most 200; None when the note is not the student's."""
    if not Note.objects.filter(pk=note_id, user_id=user_id).exists():
        return None
    return list(NoteVersion.objects.filter(note_id=note_id, user_id=user_id).order_by("-rev")[:VERSION_LIST_LIMIT])


def get_version(user_id, note_id, rev: int) -> NoteVersion | None:
    return NoteVersion.objects.filter(note_id=note_id, user_id=user_id, rev=rev).first()


def changes(user_id, *, since: str | None = None, limit: int = 200) -> tuple[list[Note], str | None, bool]:
    """
    Offline-cache feed: every note (trashed ones too, so the client learns about deletes) changed after `since`, oldest
    first. Returns `(notes, next_since, has_more)`. The cursor is `(updated_at, id)`, never a client clock.
    """
    limit = max(1, min(limit, 500))
    qs = Note.objects.filter(user_id=user_id)
    parts = decode_cursor(since)
    if parts:
        ts, last_id = parse_ts(parts[0]), str(parts[1])
        qs = qs.filter(Q(updated_at__gt=ts) | Q(updated_at=ts, id__gt=last_id))
    rows = list(qs.order_by("updated_at", "id")[: limit + 1])
    more = len(rows) > limit
    rows = rows[:limit]
    last: Any = rows[-1] if rows else None
    next_since = encode_cursor([last.updated_at, last.id]) if last else since
    return rows, next_since, more
