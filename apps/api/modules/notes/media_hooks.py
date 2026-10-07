"""
What notes does when `media` decides about a PDF upload (ERD 1.2 lifecycle). Both hooks run after commit, are idempotent and
only move a document forward: a replay, a retry or a late hook never undoes a later state.

    pdf_clean(attachment_id)               scanning -> inspecting, and queue the heavy `notes.inspect` job (worker)
    pdf_rejected(attachment_id, reason)    any live state -> rejected with the reason shown to the student
"""

from __future__ import annotations

import uuid

from django.utils import timezone

from core import jobs

from .jobs import JOB_INSPECT
from .models import Document

REASONS = frozenset(
    {"type_mismatch", "malware", "pdf_corrupt", "too_many_pages", "too_large", "decode_failed", "policy"}
)


def pdf_clean(attachment_id: uuid.UUID) -> None:
    waiting = [Document.Status.RESERVED, Document.Status.SCANNING]
    Document.objects.filter(attachment_id=attachment_id, status__in=waiting).update(
        status=Document.Status.INSPECTING, updated_at=timezone.now()
    )
    for document_id in Document.objects.filter(attachment_id=attachment_id).values_list("id", flat=True):
        jobs.enqueue(JOB_INSPECT, {"document_id": str(document_id)}, dedupe_key=f"{JOB_INSPECT}:{document_id}")


def pdf_rejected(attachment_id: uuid.UUID, reason: str) -> None:
    Document.objects.filter(attachment_id=attachment_id).exclude(status=Document.Status.REJECTED).update(
        status=Document.Status.REJECTED,
        status_reason=reason if reason in REASONS else "policy",
        updated_at=timezone.now(),
    )
