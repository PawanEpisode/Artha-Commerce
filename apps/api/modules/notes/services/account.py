"""Data rights (DPDP, FR-F03-70): everything notes holds for a student, exported or erased. Never gated by the flag."""

from __future__ import annotations

from modules.media import services as media

from ..models import (
    AiJob,
    Annotation,
    Document,
    DocumentChapter,
    ExportJob,
    ItemTag,
    MonthlyUsage,
    Note,
    NoteImage,
    NoteVersion,
    QuotaUsage,
    ReanchorItem,
    Settings,
    Tag,
)
from . import content


def export_for_user(user_id) -> dict:
    from .. import selectors  # local: selectors import the services' quota helpers

    return selectors.export_all(user_id)


def delete_all_for_user(user_id) -> dict:
    """
    Removes notes (trash included), versions, image rows, documents with their marks, page ranges and export jobs, tags and
    their links, settings and usage. Every file the student owns (note images, PDFs, covers, exports) is queued for deletion
    through `media`: the objects leave storage within the next worker or tick runs, which is well inside 24 hours. Derived
    file content shared with other students' identical files is not touched; it is only marked orphaned when no document of
    anyone references it any more. Idempotent. Returns counts, the report the web shows. Only this student's rows are read
    or written: every statement is filtered by `user_id`.
    """
    image_ids = list(NoteImage.objects.filter(user_id=user_id).values_list("attachment_id", flat=True).distinct())
    documents = list(
        Document.objects.filter(user_id=user_id).values_list("attachment_id", "cover_attachment_id", "content_id")
    )
    pdf_ids = [a for a, _, _ in documents]
    cover_ids = [c for _, c, _ in documents if c]
    content_ids = {c for _, _, c in documents if c}
    export_ids = [
        a
        for a in ExportJob.objects.filter(user_id=user_id, attachment__isnull=False).values_list(
            "attachment_id", flat=True
        )
    ]
    report = {
        "notes": Note.objects.filter(user_id=user_id).count(),
        "versions": NoteVersion.objects.filter(user_id=user_id).count(),
        "images": len(image_ids),
        "tags": Tag.objects.filter(user_id=user_id).count(),
        "settings": Settings.objects.filter(pk=user_id).count(),
        "documents": len(documents),
        "marks": Annotation.objects.filter(user_id=user_id).count(),
        "page_ranges": DocumentChapter.objects.filter(user_id=user_id).count(),
        "exports": ExportJob.objects.filter(user_id=user_id).count(),
        "ai_jobs": AiJob.objects.filter(user_id=user_id).count(),
        "reanchor_items": ReanchorItem.objects.filter(user_id=user_id).count(),
        "files": len({*image_ids, *pdf_ids, *cover_ids, *export_ids}),
    }
    media.queue_delete({*image_ids, *pdf_ids, *cover_ids, *export_ids})
    ItemTag.objects.filter(user_id=user_id).delete()
    AiJob.objects.filter(user_id=user_id).delete()
    ReanchorItem.objects.filter(user_id=user_id).delete()
    ExportJob.objects.filter(user_id=user_id).delete()
    DocumentChapter.objects.filter(user_id=user_id).delete()
    Annotation.objects.filter(user_id=user_id).delete()
    Document.objects.filter(user_id=user_id).delete()
    report["contents_orphaned"] = content.mark_orphaned(content_ids)
    Note.objects.filter(user_id=user_id).delete()  # cascades versions and image rows
    Tag.objects.filter(user_id=user_id).delete()
    Settings.objects.filter(pk=user_id).delete()
    MonthlyUsage.objects.filter(user_id=user_id).delete()
    QuotaUsage.objects.filter(pk=user_id).delete()
    return report
