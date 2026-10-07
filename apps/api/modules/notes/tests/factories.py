"""Row builders for tests that need documents, marks and the rows around them without going through services."""

from __future__ import annotations

import uuid

from modules.media.models import Attachment
from modules.notes.models import Annotation, Document, ExportJob, FileContent, Note, Tag

ALICE = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
BOB = uuid.UUID("9a0d1c34-2b7f-4c58-8e61-5d3f7a2b9c22")


def make_attachment(user_id, *, kind="note_pdf", bytes=1000, status="clean", mime="application/pdf", ext="pdf"):  # noqa: A002
    attachment_id = uuid.uuid4()
    return Attachment.objects.create(
        id=attachment_id,
        user_id=user_id,
        kind=kind,
        bucket="notes-private",
        path=f"{user_id}/test/{attachment_id}.{ext}",
        bytes=bytes,
        mime=mime,
        status=status,
    )


def make_document(user_id, **fields) -> Document:
    attachment = fields.pop("attachment", None) or make_attachment(user_id)
    defaults = {"title": "A PDF", "bytes": attachment.bytes, "status": "ready", "page_count": 10}
    return Document.objects.create(user_id=user_id, attachment=attachment, **{**defaults, **fields})


def make_content(**fields) -> FileContent:
    sha = fields.pop("sha256", uuid.uuid4().hex + uuid.uuid4().hex)
    return FileContent.objects.create(sha256=sha, bytes=fields.pop("bytes", 1000), **fields)


def make_annotation(document: Document, **fields) -> Annotation:
    defaults = {
        "user_id": document.user_id,
        "page": 1,
        "kind": "highlight",
        "geometry": {"v": 1, "rects": []},
        "color": "y",
        "seq": 1,
    }
    return Annotation.objects.create(document=document, **{**defaults, **fields})


def make_note(user_id, **fields) -> Note:
    return Note.objects.create(user_id=user_id, client_id=uuid.uuid4(), **fields)


def make_tag(user_id, name="tag") -> Tag:
    return Tag.objects.create(user_id=user_id, name=name, name_norm=name.lower())


def make_export(document: Document, **fields) -> ExportJob:
    return ExportJob.objects.create(user_id=document.user_id, document=document, **fields)
