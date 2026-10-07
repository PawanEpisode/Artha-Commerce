"""
Reads of documents (ERD 3.2): the library list, one document with its signed URL, ranges, the cheap processing poll and the
page text window. Derived facts (page sizes, flags, text and OCR progress) live on the shared `FileContent` and are folded into
the document's view here, so a second student's identical file shows as ready the moment it is linked.

`duplicate_of` is computed at read time: the earliest other LIVE document of the same student whose content has the same hash.
Signed URLs are issued only to the owner (every query is scoped by `user_id`); a cover that cannot be signed is simply absent.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.db.models import F, Q, QuerySet

from modules.media import services as media
from modules.media.errors import NotReady, StorageUnavailable
from modules.media.models import Attachment

from ..models import Document, DocumentChapter, FileContent, FilePage, ItemTag, Tag
from ._common import LinkView, Page, clamp_limit, decode_cursor, encode_cursor, link_views

logger = logging.getLogger(__name__)

OPENABLE = ("inspecting", "ready", "needs_password")  # the file may be read: a stuck inspection still opens (ERD 6.5)
MAX_TEXT_PAGES = 20
WORD_DECIMALS = 4


@dataclass(frozen=True)
class DocumentFilter:
    level_id: Any = None
    subject_key: str | None = None
    chapter_key: str | None = None
    tag_id: Any = None
    status: str | None = None
    source: str | None = None
    q: str = ""
    trashed: bool = False
    sort: str = "recent"


@dataclass(frozen=True)
class DocumentView:
    document: Document
    link: LinkView
    tags: tuple[Tag, ...] = ()
    content: FileContent | None = None
    cover_url: str | None = None
    duplicate_of: Any = None
    # detail only
    can_open: bool = False
    file_url: str | None = None
    file_url_expires_at: datetime | None = None
    ranges: tuple[tuple[DocumentChapter, LinkView], ...] = ()


@dataclass(frozen=True)
class Processing:
    status: str
    status_reason: str | None
    text_status: str
    text_pages_done: int
    ocr_status: str
    ocr_pages_done: int
    ocr_pages_total: int
    page_count: int | None
    is_scanned: bool | None


@dataclass(frozen=True)
class TextPage:
    page: int
    text: str
    source: str
    conf: int | None
    words: list | None


@dataclass(frozen=True)
class PageText:
    pages: list[TextPage] = field(default_factory=list)
    text_status: str = "pending"
    ocr_status: str = "none"


# --- Querysets ------------------------------------------------------------------------------------------------------------
def owned(user_id) -> QuerySet[Document]:
    return Document.objects.filter(user_id=user_id)


def live(user_id) -> QuerySet[Document]:
    return owned(user_id).filter(deleted_at__isnull=True)


def _filtered(user_id, f: DocumentFilter) -> QuerySet[Document]:
    qs = owned(user_id).select_related("content", "attachment")
    if f.trashed:
        qs = qs.filter(deleted_at__isnull=False)
    else:
        qs = qs.filter(deleted_at__isnull=True)
        if not f.status:
            qs = qs.exclude(status=Document.Status.EXPIRED)  # an abandoned upload is not a library entry
    if f.status:
        qs = qs.filter(status=f.status)
    if f.source:
        qs = qs.filter(source_kind=f.source)
    if f.level_id:
        qs = qs.filter(level_id=f.level_id)
    if f.subject_key:
        qs = qs.filter(subject_key=f.subject_key)
    if f.chapter_key:
        qs = qs.filter(chapter_key=f.chapter_key)
    if f.tag_id:
        qs = qs.filter(item_tags__tag_id=f.tag_id)
    if f.q.strip():
        qs = qs.filter(Q(title__icontains=f.q.strip()) | Q(original_filename__icontains=f.q.strip()))
    return qs


def _ordered(qs: QuerySet[Document], f: DocumentFilter) -> QuerySet[Document]:
    if f.trashed:
        return qs.order_by("-deleted_at", "id")
    if f.sort == "title":
        return qs.order_by("title", "id")
    return qs.order_by(F("last_opened_at").desc(nulls_last=True), "-created_at", "id")


# --- Views ----------------------------------------------------------------------------------------------------------------
def _sign_cover(document: Document) -> str | None:
    if not document.cover_attachment_id:
        return None
    try:
        return media.signed_url(document.user_id, document.cover_attachment_id).url
    except (NotReady, StorageUnavailable):
        return None
    except Exception:  # noqa: BLE001 - a missing cover row or object must never fail the list
        logger.warning("Cover could not be signed")
        return None


def _duplicates(user_id, documents: Sequence[Document]) -> dict[Any, Any]:
    """`{document id: id of the earliest other live document with the same content}` for the documents that have one."""
    content_ids = {d.content_id for d in documents if d.content_id}
    if not content_ids:
        return {}
    rows = (
        live(user_id)
        .filter(content_id__in=content_ids)
        .order_by("created_at", "id")
        .values_list("id", "content_id", "created_at")
    )
    first: dict[Any, tuple] = {}
    for doc_id, content_id, created in rows:
        first.setdefault(content_id, (doc_id, created))
    out = {}
    for d in documents:
        earliest = first.get(d.content_id) if d.content_id else None
        if earliest and earliest[0] != d.id and (earliest[1], str(earliest[0])) < (d.created_at, str(d.id)):
            out[d.id] = earliest[0]
    return out


def _views(user_id, documents: Sequence[Document], *, covers: bool = True) -> list[DocumentView]:
    if not documents:
        return []
    tag_map: dict[Any, list[Tag]] = {}
    for item in (
        ItemTag.objects.filter(document_id__in=[d.id for d in documents]).select_related("tag").order_by("tag__name")
    ):
        tag_map.setdefault(item.document_id, []).append(item.tag)
    duplicates = _duplicates(user_id, documents)
    return [
        DocumentView(
            d,
            link,
            tuple(tag_map.get(d.id, ())),
            d.content if d.content_id else None,
            _sign_cover(d) if covers else None,
            duplicates.get(d.id),
        )
        for d, link in zip(documents, link_views(documents), strict=True)
    ]


def list_documents(
    user_id, f: DocumentFilter | None = None, *, cursor: str | None = None, limit: int | None = None
) -> Page[DocumentView]:
    """The library, `recent` (last opened first, never-opened by creation date) or `title`. The cursor is an offset."""
    f = f or DocumentFilter()
    limit = clamp_limit(limit, 30)
    offset = (decode_cursor(cursor) or [0])[0]
    if not isinstance(offset, int) or offset < 0:
        offset = 0
    rows = list(_ordered(_filtered(user_id, f), f).distinct()[offset : offset + limit + 1])
    more = len(rows) > limit
    return Page(_views(user_id, rows[:limit]), encode_cursor([offset + limit]) if more else None)


def get_document(user_id, document_id) -> DocumentView | None:
    """One document with ranges and, when the file may be read, a signed URL (4 h, from `media`). None for anyone else's."""
    document = owned(user_id).select_related("content", "attachment").filter(pk=document_id).first()
    if document is None:
        return None
    view = _views(user_id, [document])[0]
    attachment = document.attachment
    can_open = attachment.status == Attachment.Status.CLEAN and document.status in OPENABLE
    file_url = expires = None
    if can_open:
        # A platform document's file belongs to the publishing module: it is read as its owner, after our own access check.
        signed = media.signed_url(attachment.user_id, attachment.id)
        file_url, expires = signed.url, signed.expires_at
    ranges = list(DocumentChapter.objects.filter(document=document).order_by("page_from", "id"))
    range_links = link_views(ranges)
    return DocumentView(
        view.document,
        view.link,
        view.tags,
        view.content,
        view.cover_url,
        view.duplicate_of,
        can_open,
        file_url,
        expires,
        tuple(zip(ranges, range_links, strict=True)),
    )


def largest_documents(user_id, limit: int = 5) -> list[dict]:
    """The five biggest documents (trashed included) for the quota sheet, `{id, title, bytes}`."""
    rows = (
        owned(user_id)
        .filter(origin=Document.Origin.UPLOAD)
        .exclude(status__in=[Document.Status.REJECTED, Document.Status.EXPIRED])
        .order_by("-bytes", "id")[:limit]
    )
    return [{"id": d.id, "title": d.title, "bytes": d.bytes} for d in rows]


# --- Progress and text -------------------------------------------------------------------------------------------------------
def get_processing(user_id, document_id) -> Processing | None:
    """The cheap poll while a file is being prepared: statuses and counters, one row."""
    d = owned(user_id).select_related("content").filter(pk=document_id).first()
    if d is None:
        return None
    c = d.content if d.content_id else None
    return Processing(
        d.status,
        d.status_reason,
        c.text_status if c else "pending",
        c.text_pages_done if c else 0,
        c.ocr_status if c else "none",
        c.ocr_pages_done if c else 0,
        c.ocr_pages_total if c else 0,
        d.page_count,
        c.is_scanned if c else None,
    )


def _words(words: list | None) -> list | None:
    if not words:
        return None
    return [
        [round(x, WORD_DECIMALS), round(y, WORD_DECIMALS), round(w, WORD_DECIMALS), round(h, WORD_DECIMALS), t]
        for x, y, w, h, t in words
    ]


def get_page_text(user_id, document_id, page_from: int, page_to: int) -> PageText | None:
    """
    Text of pages `page_from..page_to` (at most 20) of the student's document. Word boxes only for OCR pages. Pages that are
    not extracted yet are simply absent, with `text_status` telling the reader why.
    """
    if page_to - page_from + 1 > MAX_TEXT_PAGES or page_from < 1 or page_to < page_from:
        raise ValueError("Ask for 1 to 20 pages.")
    d = owned(user_id).select_related("content").filter(pk=document_id).first()
    if d is None:
        return None
    if not d.content_id:
        return PageText()
    rows = FilePage.objects.filter(content_id=d.content_id, page__gte=page_from, page__lte=page_to).order_by("page")
    pages = [
        TextPage(p.page, p.text, p.text_source, p.ocr_conf, _words(p.words) if p.text_source == "ocr" else None)
        for p in rows
    ]
    return PageText(pages, d.content.text_status, d.content.ocr_status)


def document_views(user_id, documents: Sequence[Document], *, covers: bool = True) -> list[DocumentView]:
    """Documents of the student with their link, tags, content facts and (optionally) signed cover: for the aggregate and overview."""
    return _views(user_id, documents, covers=covers)
