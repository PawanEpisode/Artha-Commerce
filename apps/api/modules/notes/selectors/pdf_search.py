"""
Search over the text of PDFs and over the student's marks (ERD 5 Q-6, 6.3).

PDF text is shared by identical files (`FilePage` is keyed by content), so the query starts from the student's own live
documents, collects their content ids and probes the `(content_id, tsv)` index for those ids only: nothing of a file the
student does not own can match, even when another student holds the same bytes. At most 5 pages per document and 100 hits come
back, ranked; snippets are made by `ts_headline` for the top 20 and in Python for the rest. A query matches in either text
configuration (English stems, or the simple one the Hindi and mixed pages use). On SQLite (quick tests) every term must occur
as a substring and the rank is flat. A reference such as `17(5)` or `Ind AS 115` is phrase matched (`domain.search_query`).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import reduce
from operator import or_
from typing import Any

from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db import connection
from django.db.models import F, Q, QuerySet, Window
from django.db.models.functions import RowNumber

from ..domain.search_query import clean_query, config_for, make_snippet, prepare_query, terms
from ..models import Annotation, Document, FileContent, FilePage
from ._common import LinkView, NoteFilter, link_views
from .documents import live, owned

MAX_HITS = 100
PAGES_PER_DOCUMENT = 5
HEADLINE_TOP = 20
SNIPPET_WIDTH = 160
INDEXING_STATUSES = ("pending", "running")
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class PdfHit:
    document: Document
    page: int
    snippet: str
    rank: float
    link: LinkView


@dataclass(frozen=True)
class MarkHit:
    annotation: Annotation
    document: Document
    snippet: str
    rank: float
    link: LinkView


@dataclass(frozen=True)
class PdfSearch:
    hits: list[PdfHit] = field(default_factory=list)
    indexing_documents: int = 0
    not_searchable: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentSearch:
    items: list[dict]
    text_status: str
    ocr_status: str
    indexed_pages: int
    page_count: int | None


# --- Query building ---------------------------------------------------------------------------------------------------------
def _query(q: str, configs: Sequence[str] = ("english", "simple")) -> SearchQuery:
    prepared = prepare_query(q)
    return reduce(or_, [SearchQuery(prepared, config=c, search_type="websearch") for c in configs])


def _substring(qs: QuerySet, q: str, *columns: str) -> QuerySet:
    for term in terms(q):
        qs = qs.filter(reduce(or_, [Q(**{f"{c}__icontains": term}) for c in columns]))
    return qs


def _ranked_pages(content_ids: Sequence[Any], q: str, *, per_content: int | None, limit: int) -> list[tuple]:
    """`[(content_id, page, rank)]` best first, at most `limit`, and at most `per_content` per file when given."""
    pages = FilePage.objects.filter(content_id__in=list(content_ids))
    if connection.vendor != "postgresql":
        seen: dict[Any, int] = {}
        out = []
        for content_id, page in (
            _substring(pages, q, "text").order_by("content_id", "page").values_list("content_id", "page")
        ):
            if per_content is None or seen.get(content_id, 0) < per_content:
                seen[content_id] = seen.get(content_id, 0) + 1
                out.append((content_id, page, 1.0))
        return out[:limit]
    query = _query(q)
    ranked = pages.filter(tsv=query).annotate(rank=SearchRank(F("tsv"), query, cover_density=True))
    if per_content is not None:
        ranked = ranked.annotate(
            nth=Window(RowNumber(), partition_by=F("content_id"), order_by=[F("rank").desc(), F("page").asc()])
        ).filter(nth__lte=per_content)
    rows = ranked.order_by("-rank", "content_id", "page").values_list("content_id", "page", "rank")[:limit]
    return [(c, p, float(r)) for c, p, r in rows]


# --- Snippets ----------------------------------------------------------------------------------------------------------------
def _tidy(text: str) -> str:
    flat = _SPACES.sub(" ", text).strip()
    return flat if len(flat) <= SNIPPET_WIDTH * 2 else flat[: SNIPPET_WIDTH * 2].rstrip() + "…"


def snippets_for(pairs: Sequence[tuple], q: str) -> dict[tuple, str]:
    """
    `{(content_id, page): snippet}` as plain text (no markup: the web marks the words itself). The top 20 come from
    `ts_headline`, in the configuration of each page's language; the others are cut around the first matching word.
    """
    if not pairs:
        return {}
    where = reduce(or_, [Q(content_id=c, page=p) for c, p in pairs])
    rows = list(FilePage.objects.filter(where).values_list("content_id", "page", "lang", "text"))
    by_key = {(c, p): (lang, text) for c, p, lang, text in rows}
    out: dict[tuple, str] = {}
    top = [(c, p) for c, p in pairs[:HEADLINE_TOP] if (c, p) in by_key]
    if connection.vendor == "postgresql" and top:
        langs = {by_key[k][0] for k in top}
        for lang in langs:
            config = config_for(lang)
            headline = SearchHeadline(
                "text",
                SearchQuery(prepare_query(q), config=config, search_type="websearch"),
                config=config,
                start_sel="",
                stop_sel="",
                max_words=30,
                min_words=12,
                max_fragments=1,
            )
            cond = reduce(or_, [Q(content_id=c, page=p) for c, p in top if by_key[(c, p)][0] == lang])
            for c, p, text in FilePage.objects.filter(cond).annotate(h=headline).values_list("content_id", "page", "h"):
                out[(c, p)] = _tidy(text)
    words = terms(q)
    for key in pairs:
        if key not in out and key in by_key:
            out[key] = make_snippet(by_key[key][1], words, SNIPPET_WIDTH)
    return out


# --- In one document -----------------------------------------------------------------------------------------------------------
def search_document(user_id, document_id, q: str, limit: int = 50) -> DocumentSearch | None:
    """`GET documents/{id}/search/`: ranked pages of the student's document. None for anyone else's."""
    d = owned(user_id).select_related("content").filter(pk=document_id).first()
    if d is None:
        return None
    c: FileContent | None = d.content if d.content_id else None
    if c is None:
        return DocumentSearch([], "pending", "none", 0, d.page_count)
    indexed = FilePage.objects.filter(content_id=c.id).count()
    hits = _ranked_pages([c.id], q, per_content=None, limit=limit) if clean_query(q) else []
    snippets = snippets_for([(cid, p) for cid, p, _ in hits], q)
    items = [{"page": p, "snippet": snippets.get((cid, p), ""), "rank": round(r, 4)} for cid, p, r in hits]
    return DocumentSearch(items, c.text_status, c.ocr_status, indexed, c.page_count or d.page_count)


# --- Across the library ---------------------------------------------------------------------------------------------------------
def _not_searchable_reason(d: Document) -> str | None:
    """Why a live document cannot be searched yet (or None when it can): `locked`, `scanned` or `pending`."""
    c = d.content if d.content_id else None
    if d.status == Document.Status.NEEDS_PASSWORD or (c and c.text_status == "locked"):
        return "locked"
    if c is None or c.text_status in INDEXING_STATUSES or c.text_status == "failed":
        return "pending"
    if c.is_scanned and c.ocr_status in ("none", "failed"):
        return "scanned"
    if c.is_scanned and c.ocr_status in INDEXING_STATUSES:
        return "pending"
    return None


def _in_scope(qs: QuerySet, flt: NoteFilter | None) -> QuerySet:
    """The syllabus filters of the search request (level, subject, chapter) on any rows with link columns."""
    if flt is None:
        return qs
    for column, value in (
        ("level_id", flt.level_id),
        ("subject_key", flt.subject_key),
        ("chapter_key", flt.chapter_key),
    ):
        if value:
            qs = qs.filter(**{column: value})
    return qs


def search_pdf(user_id, q: str, *, limit: int = MAX_HITS, flt: NoteFilter | None = None) -> PdfSearch:
    """Ranked page hits across the student's live documents, plus what could not be searched and why."""
    docs = list(
        _in_scope(live(user_id), flt)
        .filter(status__in=[Document.Status.INSPECTING, Document.Status.READY, Document.Status.NEEDS_PASSWORD])
        .select_related("content")
        .order_by("created_at", "id")
    )
    reasons = {d.id: _not_searchable_reason(d) for d in docs}
    meta = [{"document_id": d.id, "reason": reasons[d.id]} for d in docs if reasons[d.id]]
    indexing = sum(1 for d in docs if reasons[d.id] == "pending")
    if not clean_query(q):
        return PdfSearch([], indexing, meta)
    owner_of: dict[Any, Document] = {}  # one document answers for a file the student holds twice
    for d in docs:
        if d.content_id and reasons[d.id] != "locked":
            owner_of.setdefault(d.content_id, d)
    ranked = _ranked_pages(list(owner_of), q, per_content=PAGES_PER_DOCUMENT, limit=min(limit, MAX_HITS))
    snippets = snippets_for([(c, p) for c, p, _ in ranked], q)
    by_doc = {d.id: d for d in owner_of.values()}
    links = dict(zip(by_doc, link_views(list(by_doc.values())), strict=True))
    hits = [PdfHit(owner_of[c], p, snippets.get((c, p), ""), r, links[owner_of[c].id]) for c, p, r in ranked]
    return PdfSearch(hits, indexing, meta)


# --- Marks ---------------------------------------------------------------------------------------------------------------------
def search_marks(user_id, q: str, *, limit: int = MAX_HITS, flt: NoteFilter | None = None) -> list[MarkHit]:
    """Text marks (highlight, underline, area, sticky, textbox) whose quote or comment match; live marks of live documents only."""
    if not clean_query(q):
        return []
    qs = Annotation.objects.filter(
        user_id=user_id,
        deleted_at__isnull=True,
        kind__in=Annotation.LISTED_KINDS,
        document__user_id=user_id,
        document__deleted_at__isnull=True,
    ).select_related("document")
    qs = _in_scope(qs, flt)
    if connection.vendor == "postgresql":
        query = _query(q)
        qs = (
            qs.filter(search_tsv=query)
            .annotate(rank=SearchRank(F("search_tsv"), query, cover_density=True))
            .order_by("-rank", "-updated_at", "id")
        )
    else:
        qs = _substring(qs, q, "quote_exact", "comment").order_by("-updated_at", "id")
    rows = list(qs[: min(limit, MAX_HITS)])
    words = terms(q)
    return [
        MarkHit(
            a,
            a.document,
            make_snippet(f"{a.quote_exact or ''} {a.comment or ''}", words, SNIPPET_WIDTH),
            float(getattr(a, "rank", 1.0)),
            link,
        )
        for a, link in zip(rows, link_views(rows), strict=True)
    ]
