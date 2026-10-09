"""
Input validation (DRF serializers) and output shapes for /api/v1/notes/. Output builders are plain functions over the
selectors' result types, so the JSON shape is defined in one place and documented in docs/F-03-API-CONTRACT.md.
"""

from __future__ import annotations

from rest_framework import serializers

from .domain.chapter_suggest import Suggestion
from .domain.legend import COLOR_KEYS, legend_problems
from .domain.search_query import MAX_QUERY
from .domain.tags import MAX_NAME
from .models import Note, NoteVersion, Settings, Tag
from .selectors import (
    AggregateItem,
    ChapterCountRow,
    ChapterCounts,
    ChapterOverview,
    LinkView,
    NoteCard,
    SearchHit,
    SubjectCounts,
    TagView,
    UsageView,
)
from .services.settings import capabilities

MARK_COLORS = ["y", "g", "b", "p", "o", "i1", "i2", "i3", "i4", "i5"]  # markup keys and ink keys (ERD 2.6)
MAX_BODY = 250_000  # a transport bound; the real limit (100,000 characters) is a lint error with a message


# --- Input ------------------------------------------------------------------------------------------------------------
class NoteListQuery(serializers.Serializer):
    level = serializers.UUIDField(required=False)
    subject = serializers.SlugField(required=False)
    chapter = serializers.SlugField(required=False)
    topic = serializers.SlugField(required=False)
    tag = serializers.UUIDField(required=False)
    unfiled = serializers.BooleanField(required=False, default=False)
    kind = serializers.ChoiceField(choices=[c.value for c in Note.Kind], required=False)
    pinned = serializers.BooleanField(required=False, default=None, allow_null=True)
    trashed = serializers.BooleanField(required=False, default=False)
    q = serializers.CharField(required=False, allow_blank=True, max_length=MAX_QUERY, default="")
    cursor = serializers.CharField(required=False, allow_blank=True, max_length=400)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100)

    def validate(self, attrs):
        if (attrs.get("subject") or attrs.get("chapter") or attrs.get("topic")) and not attrs.get("level"):
            raise serializers.ValidationError({"level": "Required when filtering by subject, chapter or topic."})
        return attrs


class AggregateQuery(NoteListQuery):
    tab = serializers.ChoiceField(choices=["all", "notes", "highlights", "documents"], required=False, default="all")
    color = serializers.ChoiceField(choices=MARK_COLORS, required=False)  # R2: marks only
    doc = serializers.UUIDField(required=False)  # R2

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `from` and `to` are the public query names but not valid Python identifiers for class attributes.
        self.fields["from"] = serializers.DateField(required=False)
        self.fields["to"] = serializers.DateField(required=False)


class NoteCreateSerializer(serializers.Serializer):
    """`POST notes/` (optional `id`) and the body of `PUT notes/{id}/` (the id is in the path). `client_id` defaults to the id."""

    id = serializers.UUIDField(required=False)
    client_id = serializers.UUIDField(required=False)
    title = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    body_md = serializers.CharField(
        required=False, allow_blank=True, max_length=MAX_BODY, default="", trim_whitespace=False
    )
    chapter_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    topic_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    tag_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=20, default=list)

    def __init__(self, *args, path_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.path_id = path_id

    def validate(self, attrs):
        if self.path_id is not None:
            attrs["id"] = self.path_id
        if "id" not in attrs and "client_id" not in attrs:
            raise serializers.ValidationError({"client_id": "Send a client_id or an id."})
        return attrs


class NotePatchSerializer(serializers.Serializer):
    base_rev = serializers.IntegerField(min_value=1)
    base_body_md = serializers.CharField(required=False, allow_blank=True, max_length=MAX_BODY, trim_whitespace=False)
    base = serializers.DictField(required=False, child=serializers.JSONField())
    title = serializers.CharField(required=False, allow_blank=True, max_length=200)
    body_md = serializers.CharField(required=False, allow_blank=True, max_length=MAX_BODY, trim_whitespace=False)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    topic_id = serializers.UUIDField(required=False, allow_null=True)
    pinned = serializers.BooleanField(required=False)
    tag_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=20)
    source = serializers.ChoiceField(choices=["autosave", "manual"], required=False, default="autosave")
    resolution = serializers.ChoiceField(choices=["mine", "theirs", "both"], required=False, allow_null=True)

    FIELDS = ("title", "body_md", "chapter_id", "topic_id", "pinned", "tag_ids")

    def patch(self) -> dict:
        """Only the note fields the client actually sent, so omitted fields stay untouched."""
        return {k: self.validated_data[k] for k in self.FIELDS if k in self.validated_data}


class ClipSource(serializers.Serializer):
    module = serializers.CharField(max_length=40)
    ref = serializers.CharField(max_length=120)
    label = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")


class ClipSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    text_md = serializers.CharField(max_length=MAX_BODY, trim_whitespace=False)
    source = ClipSource()
    chapter_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    topic_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    tag_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=20, default=list)


class ChangesQuery(serializers.Serializer):
    since = serializers.CharField(required=False, allow_blank=True, max_length=400)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500, default=200)


class CountsQuery(serializers.Serializer):
    level = serializers.UUIDField()
    subject = serializers.SlugField()


class SearchQuery(serializers.Serializer):
    q = serializers.CharField(max_length=MAX_QUERY)
    scope = serializers.ChoiceField(choices=["all", "notes", "highlights", "pdf"], required=False, default="all")
    level = serializers.UUIDField(required=False)
    subject = serializers.SlugField(required=False)
    chapter = serializers.SlugField(required=False)
    cursor = serializers.CharField(required=False, allow_blank=True, max_length=400)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)

    def validate(self, attrs):
        if (attrs.get("subject") or attrs.get("chapter")) and not attrs.get("level"):
            raise serializers.ValidationError({"level": "Required when filtering by subject or chapter."})
        return attrs


class TagCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=MAX_NAME)
    color_key = serializers.CharField(max_length=8, required=False, allow_null=True, default=None)


class TagUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=MAX_NAME, required=False)
    color_key = serializers.CharField(max_length=8, required=False, allow_null=True)


class ItemTagsSerializer(serializers.Serializer):
    item_type = serializers.ChoiceField(choices=["note"])
    item_id = serializers.UUIDField()
    tag_ids = serializers.ListField(child=serializers.UUIDField(), max_length=20)


class ChapterSuggestSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=20_000, trim_whitespace=False)
    level_id = serializers.UUIDField(required=False)


class SettingsSerializer(serializers.Serializer):
    color_legend = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)
    default_color = serializers.ChoiceField(choices=list(COLOR_KEYS), required=False)
    page_tone = serializers.ChoiceField(choices=["original", "paper", "night"], required=False)
    finger_draws = serializers.BooleanField(required=False)
    ocr_default = serializers.ChoiceField(choices=["ask", "always", "never"], required=False)
    ocr_lang = serializers.ChoiceField(choices=["eng", "eng+hin"], required=False)

    def validate_color_legend(self, value):
        problems = legend_problems(value)
        if problems:
            raise serializers.ValidationError(problems)
        return value


# --- Output -----------------------------------------------------------------------------------------------------------
def link_dict(link: LinkView) -> dict:
    return {
        "level_id": link.level_id,
        "subject_id": link.subject_id,
        "subject_key": link.subject_key,
        "subject_name": link.subject_name,
        "chapter_id": link.chapter_id,
        "chapter_key": link.chapter_key,
        "chapter_name": link.chapter_name,
        "topic_id": link.topic_id,
        "topic_key": link.topic_key,
        "topic_name": link.topic_name,
        "moved_or_removed": link.moved_or_removed,
    }


def tag_dict(tag: Tag, count: int | None = None) -> dict:
    out = {"id": tag.id, "name": tag.name, "color_key": tag.color_key}
    return out if count is None else {**out, "count": count}


def snippet_of(note: Note, width: int = 200) -> str:
    text = " ".join((note.body_text or "").split())
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def note_summary(card: NoteCard) -> dict:
    n = card.note
    return {
        "id": n.id,
        "kind": n.kind,
        "origin": n.origin,
        "title": n.title,
        "snippet": snippet_of(n),
        "body_chars": n.body_chars,
        "pinned": n.pinned,
        "is_current_summary": n.is_current_summary,
        "link": link_dict(card.link),
        "tags": [tag_dict(t) for t in card.tags],
        "rev": n.rev,
        "created_at": n.created_at,
        "updated_at": n.updated_at,
        "deleted_at": n.deleted_at,
        "purge_after": n.purge_after,
    }


def note_detail(card: NoteCard) -> dict:
    n = card.note
    return {
        **note_summary(card),
        "client_id": n.client_id,
        "body_md": n.body_md,
        "lang": n.lang,
        "clip_source": n.clip_source,
        "image_ids": list(card.image_ids),
    }


def version_row(v: NoteVersion) -> dict:
    return {"rev": v.rev, "title": v.title, "source": v.source, "chars": len(v.body_md), "created_at": v.created_at}


def version_detail(v: NoteVersion) -> dict:
    return {"rev": v.rev, "title": v.title, "body_md": v.body_md, "source": v.source, "created_at": v.created_at}


def aggregate_item(item: AggregateItem) -> dict:
    """`{type: "note" | "highlight" | "document", ...}`: the leg's own summary shape, tagged with its type."""
    from .serializers_annotations import annotation_dict  # local: those modules import this one for `link_dict`
    from .serializers_documents import document_summary

    if item.type == "highlight":
        return {"type": "highlight", **annotation_dict(item.card)}
    if item.type == "document":
        return {"type": "document", **document_summary(item.card)}
    return {"type": item.type, **note_summary(item.card)}


def search_hit(hit: SearchHit) -> dict:
    n, link = hit.card.note, hit.card.link
    return {
        "type": "note",
        "id": n.id,
        "title": n.title,
        "snippet": hit.snippet,
        "link": link_dict(link),
        "rank": round(hit.rank, 4),
        "updated_at": n.updated_at,
    }


def tag_view(v: TagView) -> dict:
    return tag_dict(v.tag, v.count)


def settings_dict(s: Settings) -> dict:
    return {
        "color_legend": s.color_legend,
        "legend_schema": s.legend_schema,
        "default_color": s.default_color,
        "page_tone": s.page_tone,
        "finger_draws": s.finger_draws,
        "ocr_default": s.ocr_default,
        "ocr_lang": s.ocr_lang,
        "capabilities": capabilities(s.user_id),
    }


def counts_dict(c: ChapterCounts) -> dict:
    return {
        "notes": c.notes,
        "highlights": c.highlights,
        "marks": c.marks,
        "documents": c.documents,
        "has_summary": c.has_summary,
        "last_noted_at": c.last_noted_at,
    }


def _count_row(r: ChapterCountRow) -> dict:
    c = r.counts
    return {
        "chapter_id": r.chapter_id,
        "chapter_key": r.chapter_key,
        "name": r.name,
        "notes": c.notes,
        "highlights": c.highlights,
        "marks": c.marks,
        "documents": c.documents,
        "has_summary": c.has_summary,
        "last_noted_at": c.last_noted_at,
    }


def subject_counts_dict(c: SubjectCounts) -> dict:
    removed = [
        {k: v for k, v in _count_row(r).items() if k not in ("chapter_id", "name", "has_summary", "last_noted_at")}
        | {"chapter_name": r.name}
        for r in c.moved_or_removed
    ]
    return {
        "subject_key": c.subject_key,
        "chapters": [_count_row(r) for r in c.chapters],
        "unfiled": c.unfiled,
        "moved_or_removed": removed,
    }


def overview_dict(o: ChapterOverview) -> dict:
    from .serializers_documents import document_summary  # local: see `aggregate_item`

    ref = o.chapter
    counts = counts_dict(o.counts)
    return {
        "chapter": {
            "id": ref.id,
            "key": ref.key,
            "name": ref.name,
            "subject_key": ref.subject_key,
            "subject_name": ref.subject_name,
            "level_id": ref.level_id,
        },
        "counts": {k: counts[k] for k in ("notes", "highlights", "marks", "documents")},
        "has_summary": counts["has_summary"],
        "last_noted_at": counts["last_noted_at"],
        "current_summary": note_summary(o.current_summary) if o.current_summary else None,
        "recent": [note_summary(c) for c in o.recent],
        "documents": [document_summary(v) for v in o.documents],
    }


def suggestion_dict(s: Suggestion) -> dict:
    c = s.candidate
    return {
        "chapter_id": c.chapter_id,
        "chapter_key": c.chapter_key,
        "chapter_name": c.chapter_name,
        "subject_id": c.subject_id,
        "subject_key": c.subject_key,
        "subject_name": c.subject_name,
        "score": s.score,
    }


def usage_dict(u: UsageView) -> dict:
    return {"plan": u.plan, "limits": u.limits, "used": u.used, "resets_on": u.resets_on.isoformat()}
