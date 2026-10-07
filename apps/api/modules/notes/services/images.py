"""The uploaded images a note references, kept in step with its body on every save (ERD 2.5)."""

from __future__ import annotations

from modules.media import services as media

from ..models import Note, NoteImage
from .body import IMAGE_KIND, Body


def sync(note: Note, body: Body) -> None:
    """Make `notes_noteimage` match the body: rows for referenced images the student owns, none for the rest."""
    alts = {}
    for ref in body.refs:
        alts.setdefault(ref.attachment_id, ref.alt)
    owned = media.clean_attachment_ids(note.user_id, alts, IMAGE_KIND)
    NoteImage.objects.filter(note=note).exclude(attachment_id__in=owned).delete()
    existing = {i.attachment_id: i for i in NoteImage.objects.filter(note=note)}
    for attachment_id in owned:
        row = existing.get(attachment_id)
        if row is None:
            NoteImage.objects.create(
                note=note, attachment_id=attachment_id, user_id=note.user_id, alt_text=alts[attachment_id]
            )
        elif row.alt_text != alts[attachment_id]:
            NoteImage.objects.filter(note=note, attachment_id=attachment_id).update(alt_text=alts[attachment_id])
