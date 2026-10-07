"""
Public write interface for marks (ERD 3.2). The rules are in `annotation_ops`; this module re-exports its entry point and holds
the two small writes that are not a student's edit: the purge of old tombstones and the cached recall card id.
"""

from __future__ import annotations

from uuid import UUID

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from ..models import Annotation, Document
from .annotation_ops import AnnotationOp, BatchResult, OpResult, apply_annotation_ops, lock_document

__all__ = [
    "AnnotationOp",
    "BatchResult",
    "OpResult",
    "apply_annotation_ops",
    "purge_expired",
    "remember_recall_card",
]


def purge_expired(*, now=None, limit: int = 200) -> int:
    """
    Hard-deletes mark tombstones whose 30 days are up (they were not counted, so no counter moves). Returns how many; callers
    repeat while it equals `limit`. A client that stayed offline longer than that never receives the tombstone, so the web
    resyncs from `since_seq=0` when its last sync is older than the trash window.
    """
    now = now or timezone.now()
    ids = list(
        Annotation.objects.filter(deleted_at__isnull=False, purge_after__lte=now).values_list("id", flat=True)[:limit]
    )
    if not ids:
        return 0
    with transaction.atomic():  # the conditions are repeated so a mark restored since the read is left alone
        deleted, _ = Annotation.objects.filter(pk__in=ids, deleted_at__isnull=False, purge_after__lte=now).delete()
    return len(ids) if deleted else 0


def remember_recall_card(user_id, annotation_id: UUID, card_id: UUID) -> None:
    """
    Caches the card on the mark. It is a change other devices should see, so it takes the document lock and a `seq`; it is
    not an edit (no `rev` bump, no `updated_at`), so a client's pending write keeps its `base_rev`.
    """
    with transaction.atomic():
        doc_id = (
            Annotation.objects.filter(pk=annotation_id, user_id=user_id).values_list("document_id", flat=True).first()
        )
        if doc_id is None:
            raise NotFound("Mark not found.")
        doc = lock_document(user_id, doc_id)
        doc.change_seq += 1
        Document.objects.filter(pk=doc.pk).update(change_seq=doc.change_seq)
        Annotation.objects.filter(pk=annotation_id).update(recall_card_id=card_id, seq=doc.change_seq)
