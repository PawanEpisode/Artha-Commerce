"""Everything notes holds for a student, as JSON-safe data (DPDP export). Search vectors never leave."""

from __future__ import annotations

from core.serialization import row_to_dict

from ..models import ItemTag, MonthlyUsage, Note, NoteVersion, QuotaUsage, Settings, Tag


def export_all(user_id) -> dict:
    tag_names: dict = {}
    for item in ItemTag.objects.filter(user_id=user_id).select_related("tag"):
        tag_names.setdefault(item.note_id, []).append(item.tag.name)
    versions: dict = {}
    for v in NoteVersion.objects.filter(user_id=user_id).order_by("rev").iterator():
        versions.setdefault(v.note_id, []).append(row_to_dict(v, exclude=frozenset({"user_id", "note_id"})))
    notes = []
    for note in Note.objects.filter(user_id=user_id).order_by("created_at", "id").iterator():
        notes.append(
            {**row_to_dict(note), "tags": sorted(tag_names.get(note.id, [])), "versions": versions.get(note.id, [])}
        )
    settings = Settings.objects.filter(pk=user_id).first()
    usage = QuotaUsage.objects.filter(pk=user_id).first()
    return {
        "notes": notes,
        "tags": [row_to_dict(t) for t in Tag.objects.filter(user_id=user_id).order_by("name_norm")],
        "settings": row_to_dict(settings) if settings else None,
        "usage": row_to_dict(usage) if usage else None,
        "monthly_usage": [row_to_dict(m) for m in MonthlyUsage.objects.filter(user_id=user_id).order_by("month")],
    }
