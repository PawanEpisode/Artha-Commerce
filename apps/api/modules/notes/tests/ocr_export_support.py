"""Shared builders for the OCR, export and archive tests: a fake object store, real generated PDFs stored in it, and documents."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest

from modules.media.models import Attachment
from modules.media.tests.conftest import FakeStorage
from modules.notes.models import Document, FileContent

from .worker.fixtures import make_pdfs as mk


@pytest.fixture
def fake_storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr("modules.media.services.get_storage", lambda: fake)
    return fake


def store_pdf(fake: FakeStorage, user_id, path: Path) -> Attachment:
    """Puts a generated PDF into the fake store under a quarantine path like the real upload, with a clean row."""
    data = Path(path).read_bytes()
    attachment_id = uuid.uuid4()
    attachment = Attachment.objects.create(
        id=attachment_id,
        user_id=user_id,
        kind="note_pdf",
        bucket="notes-private",
        path=f"quarantine/{user_id}/{attachment_id}.pdf",
        bytes=len(data),
        mime="application/pdf",
        status="clean",
    )
    fake.upload(attachment.bucket, attachment.path, data, content_type="application/pdf", cache_control="")
    return attachment


def make_pdf_document(fake, user_id, path: Path, *, content: FileContent | None = None, **content_fields) -> Document:
    """A ready document whose file is `path`. Identical bytes share one `FileContent` (pass the first document's content)."""
    data = Path(path).read_bytes()
    attachment = store_pdf(fake, user_id, path)
    if content is None:
        fields = {"page_meta_schema": 1, "text_status": "done", **content_fields}
        if "page_count" not in fields:
            fields["page_count"] = _page_count(path)
        content = FileContent.objects.create(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), **fields)
    return Document.objects.create(
        user_id=user_id,
        attachment=attachment,
        content=content,
        title="Scanned notes",
        bytes=len(data),
        status="ready",
        page_count=content.page_count,
    )


def _page_count(path: Path) -> int:
    import pikepdf

    with pikepdf.open(path) as pdf:
        return len(pdf.pages)


def scanned_document(
    fake, user_id, tmp_path, *, pages=3, lines=("INPUT TAX CREDIT", "GOODS AND SERVICES TAX"), **fields
):
    path = mk.scanned_pdf(tmp_path / f"scan-{uuid.uuid4().hex[:6]}.pdf", pages, lines=lines)
    return make_pdf_document(fake, user_id, path, is_scanned=True, can_copy=True, can_modify=True, **fields)


def run_jobs(job_types, *, limit=200) -> int:
    """Runs queued jobs of these types the way the worker loop does, until none is due (waits are not slept)."""
    from core import jobs

    ran = 0
    while ran < limit:
        job = jobs.claim_next(types=list(job_types), worker="test-worker")
        if job is None:
            return ran
        jobs.run_job(job)
        ran += 1
    return ran
