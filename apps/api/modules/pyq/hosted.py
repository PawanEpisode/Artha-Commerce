"""
Past papers the platform hosts itself (instead of linking to the institute's site): the PDF goes into the private notes
bucket as a platform-owned attachment, and the paper's `PaperLink` points at it. A student opens it from the paper page:
`open_link` adds it to their library as a platform document, so it reads in the PDF reader and takes their own marks.

The object is never public. The reader gets a short-lived signed URL after the access check, like every notes PDF.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from django.db import transaction

from core import storage
from modules.media import services as media
from modules.media.models import Attachment
from modules.notes.media_kinds import BUCKET, PDF_MIME
from modules.notes.services import documents

from .domain.sources import SourceFile
from .models import PaperLink, PyqPaper

logger = logging.getLogger(__name__)

# The owner id of platform-published files, by value like every user id. Not a person: nobody can sign in as it.
PLATFORM_OWNER_ID = uuid.UUID("00000000-0000-4000-8000-0000000000a9")
ATTACHMENT_KIND = "note_pdf"
MAX_BYTES = 200 * 1024 * 1024
_OPEN_NAMESPACE = uuid.UUID("5f0c1b1e-7a53-4a4e-9f0d-7a6d3c0c9b11")


class PdfRejected(ValueError):
    """The file is not a PDF we can publish."""


def check_pdf(data: bytes) -> None:
    if not data:
        raise PdfRejected("the file is empty")
    if len(data) > MAX_BYTES:
        raise PdfRejected(f"the file is {len(data) // (1024 * 1024)} MB; the limit is {MAX_BYTES // (1024 * 1024)} MB")
    if b"%PDF-" not in data[:1024]:
        raise PdfRejected("the file does not start with a PDF header")


def publish_pdf(
    paper: PyqPaper, source: SourceFile, *, force: bool = False, store: storage.Storage | None = None
) -> str:
    """
    Uploads one PDF and links it to the paper. Returns "published", "replaced" or "kept" (already hosted, `force` not given).
    The object is written first and removed again if the database write fails, so a failed run leaves nothing behind.
    """
    existing = paper.links.filter(link_kind=source.link_kind, attachment_id__isnull=False).first()
    if existing is not None and not force:
        return "kept"

    data = Path(source.path).read_bytes()
    check_pdf(data)

    store = store or storage.get_storage()
    attachment_id = uuid.uuid4()
    path = f"platform/pyq/{attachment_id}.pdf"  # ids only, never a file name
    store.upload(BUCKET, path, data, content_type=PDF_MIME, cache_control="private, max-age=3600")
    try:
        with transaction.atomic():
            Attachment.objects.create(
                id=attachment_id,
                user_id=PLATFORM_OWNER_ID,
                kind=ATTACHMENT_KIND,
                bucket=BUCKET,
                path=path,
                bytes=len(data),
                mime=PDF_MIME,
                status=Attachment.Status.CLEAN,
            )
            old_attachment_id = existing.attachment_id if existing else None
            if existing is not None:
                existing.delete()
            PaperLink.objects.create(
                paper=paper,
                link_kind=source.link_kind,
                label=source.label,
                url="",
                attachment_id=attachment_id,
                verified=True,
                link_status=PaperLink.LinkStatus.OK,
            )
            fields = []
            if paper.delivery != PyqPaper.Delivery.HOSTED:
                paper.delivery = PyqPaper.Delivery.HOSTED
                fields.append("delivery")
            if not paper.rights_basis:
                paper.rights_basis = PyqPaper.RightsBasis.INSTITUTE_MATERIAL
                fields.append("rights_basis")
            if fields:
                paper.save(update_fields=fields)
    except Exception:
        try:
            store.delete(BUCKET, [path])
        except storage.StorageError:
            logger.warning("pyq hosted pdf: could not remove %s after a failed write", path)
        raise
    if old_attachment_id:
        media.queue_delete([old_attachment_id])
    return "replaced" if existing is not None else "published"


def open_link(user_id, paper_id: uuid.UUID, link_id: uuid.UUID) -> uuid.UUID:
    """
    Puts a hosted paper PDF in the student's library (idempotent: the same file opens the same document) and returns the
    document id the reader opens. A link that is not hosted, or a paper that is not published, is not found.
    """
    link = (
        PaperLink.objects.select_related("paper")
        .filter(id=link_id, paper_id=paper_id, paper__status=PyqPaper.Status.PUBLISHED, attachment_id__isnull=False)
        .first()
    )
    if link is None:
        raise PaperLink.DoesNotExist("Hosted paper not found.")
    document = documents.open_platform_document(
        user_id,
        attachment_id=link.attachment_id,
        title=f"{link.paper.title} - {link.label}"[:200],
        client_id=uuid.uuid5(_OPEN_NAMESPACE, f"{user_id}:{link.attachment_id}"),
    )
    return document.id
