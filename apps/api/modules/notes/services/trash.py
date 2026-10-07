"""
Trash, restore and purge (FR-F03-36, ERD 6.4). A trashed note leaves the quota (`notes_active`) and counts at once, stays
restorable for 30 days and is then purged by the cron tick. Restoring takes a quota slot again, so trash cannot be used to
exceed the limit. Purge removes rows; the note's image files are queued for deletion unless another live note uses them.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from modules.media import services as media

from .. import events
from ..models import Note, NoteImage, NoteVersion
from . import notes, quota, search_index, versions

TRASH_DAYS = 30


@transaction.atomic
def trash_note(user_id, note_id) -> Note:
    """Idempotent: trashing a trashed note returns it unchanged."""
    note = notes.get_locked(user_id, note_id)
    if note.is_trashed:
        return note
    key = note.link_key()
    now = timezone.now()
    note.deleted_at, note.purge_after = now, now + timedelta(days=TRASH_DAYS)
    note.rev += 1
    note.save()
    quota.release_note(user_id)
    versions.record(note, source=NoteVersion.Source.MANUAL, now=now)
    events.announce_counts(user_id, [key], "trashed")
    return note


@transaction.atomic
def restore_note(user_id, note_id) -> Note:
    """Idempotent. 429 `quota_exceeded` when the student is at the note limit."""
    note = notes.get_locked(user_id, note_id)
    if not note.is_trashed:
        return note
    quota.reserve_note(user_id)
    note.deleted_at = note.purge_after = None
    note.rev += 1
    note.save()
    versions.record(note, source=NoteVersion.Source.MANUAL, now=timezone.now())
    search_index.refresh(note)
    events.announce_counts(user_id, [note.link_key()], "restored")
    return note


def purge_expired(*, now=None, limit: int = 200) -> int:
    """Hard-deletes notes whose 30 days are up. Returns how many; callers repeat while it equals `limit`."""
    now = now or timezone.now()
    ids = list(Note.objects.filter(deleted_at__isnull=False, purge_after__lte=now).values_list("id", flat=True)[:limit])
    for note_id in ids:
        _purge_one(note_id)
    return len(ids)


@transaction.atomic
def _purge_one(note_id) -> None:
    note = Note.objects.select_for_update().filter(pk=note_id, deleted_at__isnull=False).first()
    if note is None:
        return
    mine = set(NoteImage.objects.filter(note=note).values_list("attachment_id", flat=True))
    shared = set(
        NoteImage.objects.filter(attachment_id__in=mine).exclude(note=note).values_list("attachment_id", flat=True)
    )
    note.delete()  # cascades versions, image rows and tag links
    media.queue_delete(mine - shared)
