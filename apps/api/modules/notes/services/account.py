"""Data rights (DPDP, FR-F03-70): everything notes holds for a student, exported or erased. Never gated by the flag."""

from __future__ import annotations

from modules.media import services as media

from ..models import MonthlyUsage, Note, NoteImage, NoteVersion, QuotaUsage, Settings, Tag


def export_for_user(user_id) -> dict:
    from .. import selectors  # local: selectors import the services' quota helpers

    return selectors.export_all(user_id)


def delete_all_for_user(user_id) -> dict:
    """
    Removes notes (trash included), versions, image rows, tags, settings and usage, and queues the image files for deletion
    (they leave storage within the next worker or tick runs). Idempotent. Returns counts, the report the web shows.
    """
    image_ids = list(NoteImage.objects.filter(user_id=user_id).values_list("attachment_id", flat=True).distinct())
    report = {
        "notes": Note.objects.filter(user_id=user_id).count(),
        "versions": NoteVersion.objects.filter(user_id=user_id).count(),
        "images": len(image_ids),
        "tags": Tag.objects.filter(user_id=user_id).count(),
        "settings": Settings.objects.filter(pk=user_id).count(),
    }
    media.queue_delete(image_ids)
    Note.objects.filter(user_id=user_id).delete()  # cascades versions, image rows and tag links
    Tag.objects.filter(user_id=user_id).delete()
    Settings.objects.filter(pk=user_id).delete()
    MonthlyUsage.objects.filter(user_id=user_id).delete()
    QuotaUsage.objects.filter(pk=user_id).delete()
    return report
