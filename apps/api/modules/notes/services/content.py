"""
Derived file content is shared by every document with the same bytes (`FileContent`, ERD 2.2), so it outlives any one document:
it is orphaned when the last document that references it goes, and a later upload of the same bytes adopts it again. The
derived rows are purged 30 days after `orphaned_at` (a later job); until then a re-upload skips inspection and OCR.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.utils import timezone

from ..models import FileContent


def mark_orphaned(content_ids: Iterable) -> int:
    """Sets `orphaned_at` on the contents none of whose documents remain (any student's). Idempotent. Returns how many."""
    ids = [i for i in dict.fromkeys(content_ids) if i is not None]
    if not ids:
        return 0
    now = timezone.now()
    return (
        FileContent.objects.filter(pk__in=ids, orphaned_at__isnull=True, documents__isnull=True)
        .distinct()
        .update(orphaned_at=now, updated_at=now)
    )


def clear_orphaned(content_id) -> None:
    """A document references this content again (the inspect job found identical bytes): it must not be purged."""
    FileContent.objects.filter(pk=content_id, orphaned_at__isnull=False).update(
        orphaned_at=None, updated_at=timezone.now()
    )
