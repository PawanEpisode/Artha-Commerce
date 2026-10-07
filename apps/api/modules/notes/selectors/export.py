"""Everything notes holds for a student, as JSON-safe data (DPDP export). Search vectors never leave."""

from __future__ import annotations

from core.serialization import row_to_dict

from ..models import (
    Annotation,
    Document,
    DocumentChapter,
    ExportJob,
    ItemTag,
    MonthlyUsage,
    Note,
    NoteVersion,
    QuotaUsage,
    Settings,
    Tag,
)


def export_all(user_id) -> dict:
    tag_names: dict = {}  # item id (note, mark or document) -> tag names; ids are uuids, so the three never collide
    for item in ItemTag.objects.filter(user_id=user_id).select_related("tag"):
        tag_names.setdefault(item.note_id or item.annotation_id or item.document_id, []).append(item.tag.name)
    versions: dict = {}
    for v in NoteVersion.objects.filter(user_id=user_id).order_by("rev").iterator():
        versions.setdefault(v.note_id, []).append(row_to_dict(v, exclude=frozenset({"user_id", "note_id"})))
    notes = []
    for note in Note.objects.filter(user_id=user_id).order_by("created_at", "id").iterator():
        notes.append(
            {**row_to_dict(note), "tags": sorted(tag_names.get(note.id, [])), "versions": versions.get(note.id, [])}
        )
    documents = [
        {**row_to_dict(d, exclude=frozenset({"user_id"})), "tags": sorted(tag_names.get(d.id, []))}
        for d in Document.objects.filter(user_id=user_id).order_by("created_at", "id").iterator()
    ]
    marks = [
        {**row_to_dict(m, exclude=frozenset({"user_id"})), "tags": sorted(tag_names.get(m.id, []))}
        for m in Annotation.objects.filter(user_id=user_id)
        .order_by("document_id", "page", "created_at", "id")
        .iterator()
    ]
    settings = Settings.objects.filter(pk=user_id).first()
    usage = QuotaUsage.objects.filter(pk=user_id).first()
    return {
        "notes": notes,
        "documents": documents,
        "marks": marks,
        "page_ranges": [
            row_to_dict(r, exclude=frozenset({"user_id"}))
            for r in DocumentChapter.objects.filter(user_id=user_id).order_by("document_id", "page_from")
        ],
        "exports": [
            row_to_dict(e, exclude=frozenset({"user_id"}))
            for e in ExportJob.objects.filter(user_id=user_id).order_by("created_at", "id")
        ],
        "tags": [row_to_dict(t) for t in Tag.objects.filter(user_id=user_id).order_by("name_norm")],
        "settings": row_to_dict(settings) if settings else None,
        "usage": row_to_dict(usage) if usage else None,
        "monthly_usage": [row_to_dict(m) for m in MonthlyUsage.objects.filter(user_id=user_id).order_by("month")],
    }
