"""
Input validation and output shapes of the document endpoints (contract R2 "Shapes" and "Documents"). Output builders are plain
functions over the selectors' view types, like the R1 ones in `serializers.py`.
"""

from __future__ import annotations

from rest_framework import serializers

from .domain.search_query import MAX_QUERY
from .models import Document, DocumentChapter
from .selectors import DocumentSearch, DocumentView, MarkHit, PageText, PdfHit, Processing
from .serializers import link_dict, tag_dict
from .services import documents as document_services

MAX_NAME = 255
ZOOM = document_services.ZOOM
PAGE_TONES = ["original", "paper", "night"]
SOURCE_KINDS = [c.value for c in Document.SourceKind]


# --- Input --------------------------------------------------------------------------------------------------------------------
class ReserveSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    filename = serializers.CharField(max_length=MAX_NAME, trim_whitespace=True)
    bytes = serializers.IntegerField(min_value=1, max_value=2**40)
    mime = serializers.CharField(max_length=100)
    page_count_hint = serializers.IntegerField(
        min_value=1, max_value=1_000_000, required=False, allow_null=True, default=None
    )
    source_kind = serializers.ChoiceField(choices=SOURCE_KINDS, required=False, default=Document.SourceKind.OTHER)
    chapter_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    topic_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class ListQuery(serializers.Serializer):
    level = serializers.UUIDField(required=False)
    subject = serializers.SlugField(required=False)
    chapter = serializers.SlugField(required=False)
    tag = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(choices=[c.value for c in Document.Status], required=False)
    source = serializers.ChoiceField(choices=SOURCE_KINDS, required=False)
    q = serializers.CharField(required=False, allow_blank=True, max_length=MAX_QUERY, default="")
    trashed = serializers.BooleanField(required=False, default=False)
    sort = serializers.ChoiceField(choices=["recent", "title"], required=False, default="recent")
    cursor = serializers.CharField(required=False, allow_blank=True, max_length=400)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=100)


class PatchSerializer(serializers.Serializer):
    base_rev = serializers.IntegerField(min_value=1, required=False)
    title = serializers.CharField(max_length=200, required=False)
    source_kind = serializers.ChoiceField(choices=SOURCE_KINDS, required=False)
    edition_label = serializers.CharField(max_length=40, required=False, allow_null=True, allow_blank=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    topic_id = serializers.UUIDField(required=False, allow_null=True)
    tag_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=20)

    def changes(self) -> dict:
        return {k: v for k, v in self.validated_data.items() if k != "base_rev"}


class RangeSerializer(serializers.Serializer):
    page_from = serializers.IntegerField(min_value=1, max_value=100_000)
    page_to = serializers.IntegerField(min_value=1, max_value=100_000)
    chapter_id = serializers.UUIDField()
    topic_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    source = serializers.ChoiceField(choices=[c.value for c in DocumentChapter.Source], required=False, default="user")


class RangesSerializer(serializers.Serializer):
    ranges = RangeSerializer(many=True, max_length=500)


class ProgressSerializer(serializers.Serializer):
    last_page = serializers.IntegerField(min_value=1, max_value=100_000)
    last_zoom = serializers.RegexField(ZOOM, max_length=8)
    page_tone = serializers.ChoiceField(choices=PAGE_TONES, required=False, allow_null=True)


class PagesTextQuery(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `from` is the public query name but not a valid Python identifier for a class attribute.
        self.fields["from"] = serializers.IntegerField(min_value=1, max_value=100_000, required=False, default=1)
        self.fields["to"] = serializers.IntegerField(min_value=1, max_value=100_000, required=False)

    def validate(self, attrs):
        first = attrs["from"]
        last = attrs.get("to", first + 19)
        if last < first or last - first + 1 > 20:
            raise serializers.ValidationError({"to": "Ask for 1 to 20 pages."})
        return {"from": first, "to": last}


class DocumentSearchQuery(serializers.Serializer):
    q = serializers.CharField(max_length=MAX_QUERY)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=50)


# --- Output -------------------------------------------------------------------------------------------------------------------
def document_summary(v: DocumentView) -> dict:
    d, c = v.document, v.content
    return {
        "id": d.id,
        "origin": d.origin,
        "title": d.title,
        "original_filename": d.original_filename,
        "source_kind": d.source_kind,
        "edition_label": d.edition_label,
        "status": d.status,
        "status_reason": d.status_reason,
        "bytes": d.bytes,
        "page_count": d.page_count,
        "is_scanned": c.is_scanned if c else None,
        "is_encrypted": c.is_encrypted if c else False,
        "can_copy": c.can_copy if c else None,
        "can_modify": c.can_modify if c else None,
        "text_status": c.text_status if c else "pending",
        "text_pages_done": c.text_pages_done if c else 0,
        "ocr_status": c.ocr_status if c else "none",
        "ocr_pages_done": c.ocr_pages_done if c else 0,
        "ocr_pages_total": c.ocr_pages_total if c else 0,
        "ocr_mode": d.ocr_mode,
        "ocr_lang": d.ocr_lang,
        "last_page": d.last_page,
        "last_zoom": d.last_zoom,
        "page_tone": d.page_tone,
        "last_opened_at": d.last_opened_at,
        "marks_count": d.marks_count,
        "cover_url": v.cover_url,
        "duplicate_of": v.duplicate_of,
        "link": link_dict(v.link),
        "tags": [tag_dict(t) for t in v.tags],
        "rev": d.rev,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
        "deleted_at": d.deleted_at,
        "purge_after": d.purge_after,
    }


def page_range(row: DocumentChapter, link) -> dict:
    return {
        "id": row.id,
        "page_from": row.page_from,
        "page_to": row.page_to,
        "source": row.source,
        "chapter_id": link.chapter_id,
        "chapter_key": link.chapter_key,
        "subject_key": link.subject_key,
        "subject_name": link.subject_name,
        "chapter_name": link.chapter_name,
        "topic_id": link.topic_id,
        "topic_key": link.topic_key,
        "topic_name": link.topic_name,
    }


def document_detail(v: DocumentView) -> dict:
    c = v.content
    return {
        **document_summary(v),
        "client_id": v.document.client_id,
        "can_open": v.can_open,
        "file_url": v.file_url,
        "file_url_expires_at": v.file_url_expires_at,
        "page_meta": c.page_meta if c else None,
        "outline": c.outline if c else None,
        "has_javascript": c.has_javascript if c else False,
        "change_seq": v.document.change_seq,
        "ranges": [page_range(r, link) for r, link in v.ranges],
    }


def upload_dict(upload) -> dict | None:
    if upload is None:
        return None
    return {"url": upload.url, "method": "PUT", "headers": upload.headers, "expires_at": upload.expires_at}


def processing_dict(p: Processing) -> dict:
    return {
        "status": p.status,
        "status_reason": p.status_reason,
        "text_status": p.text_status,
        "text_pages_done": p.text_pages_done,
        "ocr_status": p.ocr_status,
        "ocr_pages_done": p.ocr_pages_done,
        "ocr_pages_total": p.ocr_pages_total,
        "page_count": p.page_count,
        "is_scanned": p.is_scanned,
    }


def page_text_dict(t: PageText) -> dict:
    return {
        "pages": [
            {"page": p.page, "text": p.text, "source": p.source, "conf": p.conf, "words": p.words} for p in t.pages
        ],
        "text_status": t.text_status,
        "ocr_status": t.ocr_status,
    }


def document_search_dict(s: DocumentSearch) -> dict:
    return {
        "items": s.items,
        "text_status": s.text_status,
        "ocr_status": s.ocr_status,
        "indexed_pages": s.indexed_pages,
        "page_count": s.page_count,
    }


def pdf_hit(h: PdfHit) -> dict:
    return {
        "type": "pdf",
        "document_id": h.document.id,
        "document_title": h.document.title,
        "page": h.page,
        "snippet": h.snippet,
        "rank": round(h.rank, 4),
        "link": link_dict(h.link),
    }


def mark_hit(h: MarkHit) -> dict:
    a = h.annotation
    return {
        "type": "highlight",
        "annotation_id": a.id,
        "document_id": h.document.id,
        "document_title": h.document.title,
        "page": a.page,
        "snippet": h.snippet,
        "color": a.color,
        "rank": round(h.rank, 4),
        "link": link_dict(h.link),
    }
