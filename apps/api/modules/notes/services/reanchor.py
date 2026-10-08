"""
Replace edition (PRD FR-F03-10): a newer PDF takes the place of an old one, and the student's marks follow it.

How it works
- `request_replace` is an ordinary upload (`documents.reserve_document`: same limits, same quota, same scan and inspection)
  whose document remembers `replaces_document_id`. The OLD edition is never changed or deleted: it stays in the library until
  the student trashes it, so a bad match can always be checked against the original.
- When the new file is ready the inspection queues `notes.reanchor`. For every live mark of the old edition the job decides, by
  `domain.reanchor`: text marks are found again by their quote (`domain.anchoring`) and drawn around the new words (PDFium
  rectangles, `worker.reanchor`); the others follow their page when its text is unchanged. What cannot be placed with
  confidence becomes a `ReanchorItem` ("Needs attention"): the student keeps it where it was, saves it as a note, or dismisses it.
- Idempotent and resumable: a carried mark has the id `uuid5(new document, old mark)` and an item is unique per old mark, so a
  retried job skips what is done. Page ranges are copied when both editions have the same number of pages.
- Nothing from the marks (quotes, comments) goes to logs.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import jobs as core_jobs

from .. import events
from ..domain import anchoring
from ..domain import reanchor as domain
from ..errors_replace import AlreadyResolved, NothingToSave, NotReplaceable, PageOutOfRange
from ..models import Annotation, Document, DocumentChapter, FilePage, ItemTag, ReanchorItem
from . import annotations, document_ranges, documents, objects
from . import notes as note_services

logger = logging.getLogger(__name__)

JOB_REANCHOR = "notes.reanchor"
NAMESPACE = uuid.UUID("6f1d2c9e-3b8a-4f57-9d0e-2a6c5b7e8f10")
BATCH = 40
ACTIONS = ("keep", "note", "dismiss")


def carried_id(document_id, source_id) -> uuid.UUID:
    """The id a mark gets on the new edition: stable, so the job and "keep" can be repeated without a duplicate."""
    return uuid.uuid5(NAMESPACE, f"{document_id}:{source_id}")


@dataclass(frozen=True)
class ReplaceRequest:
    document: Document
    upload: object
    created: bool


# --- The request ----------------------------------------------------------------------------------------------------------
def request_replace(
    user_id,
    old_document_id,
    *,
    client_id,
    filename: str,
    bytes: int,  # noqa: A002 - the API's own field name
    mime: str,
    page_count_hint: int | None = None,
    edition_label: str | None = None,
) -> ReplaceRequest:
    """
    Reserves the new edition (same answer as `POST documents/`). 404 for another student's document, 409 `not_replaceable` for
    one that is in the trash or not ready, and every refusal of an upload (413, 415, 422, 429) for the new file.
    """
    old = documents.get_owned(user_id, old_document_id)
    if old.deleted_at is not None or old.status != Document.Status.READY:
        raise NotReplaceable
    with transaction.atomic():
        reservation = documents.reserve_document(
            user_id,
            client_id=client_id,
            filename=filename,
            bytes=bytes,
            mime=mime,
            page_count_hint=page_count_hint,
            source_kind=old.source_kind,
            chapter_id=old.chapter_id,
            topic_id=old.topic_id,
        )
        if reservation.created:
            document = reservation.document
            document.title = old.title
            document.edition_label = (edition_label or "").strip()[:40] or None
            document.replaces_document_id = old.id
            document.reanchor_status = "waiting"
            document.save(
                update_fields=["title", "edition_label", "replaces_document_id", "reanchor_status", "updated_at"]
            )
            tag_ids = list(ItemTag.objects.filter(document=old).values_list("tag_id", flat=True))
            if tag_ids:
                documents._set_tags(user_id, document, tag_ids)
    return ReplaceRequest(reservation.document, reservation.upload, reservation.created)


def queue_reanchor(document: Document) -> None:
    """Called by the inspection when a new edition becomes ready. Safe to call twice (one job per document)."""
    if document.replaces_document_id and document.reanchor_status == "waiting":
        core_jobs.enqueue(JOB_REANCHOR, {"document_id": str(document.id)}, dedupe_key=f"{JOB_REANCHOR}:{document.id}")


# --- The job --------------------------------------------------------------------------------------------------------------
def _old_pages(old: Document) -> dict[int, tuple[str, str]]:
    """Stored text of the old edition by page, for comparing pages that carry no quote. `{page: (source, text)}`."""
    if old.content_id is None:
        return {}
    rows = FilePage.objects.filter(content_id=old.content_id).values_list("page", "text_source", "text")
    return {page: (source, text) for page, source, text in rows}


def _copy_ranges(old: Document, new: Document) -> int:
    if not old.page_count or old.page_count != new.page_count:
        return 0
    rows = list(DocumentChapter.objects.filter(document=old).order_by("page_from"))
    if not rows:
        return 0
    document_ranges.set_page_ranges(
        new.user_id,
        new.id,
        [
            {
                "page_from": r.page_from,
                "page_to": r.page_to,
                "chapter_id": r.chapter_id,
                "topic_id": r.topic_id,
                "source": r.source,
            }
            for r in rows
        ],
    )
    return len(rows)


@dataclass(frozen=True)
class Decision:
    fields: dict | None  # the new mark's fields, or None when the mark needs attention
    outcome: str  # attached | moved | needs_attention
    reason: str | None = None


def decide(mark: Annotation, edition, old_pages: dict) -> Decision:
    """Where this mark goes in the new edition. Pure given the edition's reader."""
    base = {
        "kind": mark.kind,
        "page": mark.page,
        "geometry": mark.geometry,
        "color": mark.color,
        "comment": mark.comment,
        "quote_exact": mark.quote_exact,
        "quote_prefix": mark.quote_prefix,
        "quote_suffix": mark.quote_suffix,
        "text_start": mark.text_start,
        "text_end": mark.text_end,
        "anchor_engine": mark.anchor_engine,
    }
    if mark.kind in domain.TEXT_KINDS and mark.quote_exact:
        return _decide_text(mark, edition, base)
    if mark.page > edition.page_count:
        return Decision(None, "needs_attention", "no_page")
    source, old_text = old_pages.get(mark.page, ("", ""))
    same = domain.same_page_text(old_text, edition.text(mark.page)) if source == "native" else None
    if same is True:
        return Decision(base, "attached")
    return Decision(None, "needs_attention", "page_changed" if same is False else "cannot_compare")


def _decide_text(mark: Annotation, edition, base: dict) -> Decision:
    found = domain.find_quote(
        mark.quote_exact or "",
        mark.quote_prefix or "",
        mark.quote_suffix or "",
        hint_page=mark.page,
        hint_start=mark.text_start,
        page_count=edition.page_count,
        text_of=edition.text,
    )
    if found is None:
        return Decision(None, "needs_attention", "not_found")
    if found.score < domain.ATTACH_MIN:
        return Decision(None, "needs_attention", "low_score")
    quads = edition.quads(found.page, found.start, found.end)
    if not quads:
        return Decision(None, "needs_attention", "not_found")
    if found.page == mark.page and domain.same_place(domain.old_rects(mark.kind, mark.geometry), quads):
        return Decision(base, "attached")  # exactly where it was: the student's own shape is kept
    selector = _selector(edition.text(found.page), found.start, found.end)
    moved = {**base, "page": found.page, "geometry": {"quads": quads}, **selector, "anchor_engine": None}
    return Decision(moved, "moved")


def _selector(page_text: str, start: int, end: int) -> dict:
    """Fresh quote context from the NEW page (the offsets stay unset: they are only meaningful in the browser's own text)."""
    return {
        "quote_exact": page_text[start:end][: anchoring.MAX_QUOTE],
        "quote_prefix": page_text[max(0, start - anchoring.CONTEXT_CHARS) : start],
        "quote_suffix": page_text[end : end + anchoring.CONTEXT_CHARS],
        "text_start": None,
        "text_end": None,
    }


def _op(new: Document, mark: Annotation, fields: dict, tag_ids: list):
    explicit = mark.chapter_source == Annotation.ChapterSource.EXPLICIT
    carried = {**fields}
    if explicit:
        carried["chapter_id"], carried["topic_id"] = mark.chapter_id, mark.topic_id
    return annotations.AnnotationOp(
        op="upsert", id=carried_id(new.id, mark.id), base_rev=None, fields=carried, tag_ids=tag_ids or None
    )


def _item(new: Document, mark: Annotation, reason: str) -> ReanchorItem:
    return ReanchorItem(
        user_id=new.user_id,
        document=new,
        source_annotation_id=mark.id,
        kind=mark.kind,
        page=mark.page,
        color=mark.color,
        quote_exact=mark.quote_exact,
        comment=mark.comment or "",
        geometry=mark.geometry,
        reason=reason,
    )


def run_reanchor(payload: dict) -> dict:
    """Worker handler for `notes.reanchor`. Counts only in the answer."""
    new = Document.objects.select_related("attachment").filter(pk=payload["document_id"]).first()
    if new is None or not new.replaces_document_id or new.reanchor_status not in ("waiting", "running"):
        return {"skipped": True}
    old = Document.objects.filter(pk=new.replaces_document_id, user_id=new.user_id).first()
    if new.status != Document.Status.READY or old is None:
        _finish(new, {"total": 0, "attached": 0, "moved": 0, "needs_attention": 0, "ranges_copied": 0}, failed=True)
        return {"skipped": "not_ready"}
    Document.objects.filter(pk=new.pk).update(reanchor_status="running", updated_at=timezone.now())
    marks = list(Annotation.objects.filter(document=old, deleted_at__isnull=True).order_by("page", "seq", "id"))
    ranges = _copy_ranges(old, new)
    old_pages = _old_pages(old)
    tags = {}
    for annotation_id, tag_id in ItemTag.objects.filter(annotation_id__in=[m.id for m in marks]).values_list(
        "annotation_id", "tag_id"
    ):
        tags.setdefault(annotation_id, []).append(tag_id)
    done_ids = set(Annotation.objects.filter(document=new).values_list("id", flat=True))
    done_items = set(ReanchorItem.objects.filter(document=new).values_list("source_annotation_id", flat=True))
    from ..worker import reanchor as reader

    stats = {"total": len(marks), "attached": 0, "moved": 0, "needs_attention": 0, "ranges_copied": ranges}
    with tempfile.TemporaryDirectory(prefix="reanchor-") as tmp:
        path = os.path.join(tmp, "new.pdf")
        objects.download_to(path, new.attachment, limit=new.bytes)
        with reader.open_edition(path) as edition:
            batch: list[tuple[Annotation, Decision]] = []
            for mark in marks:
                if carried_id(new.id, mark.id) in done_ids or mark.id in done_items:
                    stats["attached" if carried_id(new.id, mark.id) in done_ids else "needs_attention"] += 1
                    continue
                batch.append((mark, decide(mark, edition, old_pages)))
                core_jobs.heartbeat()
                if len(batch) >= BATCH:
                    _store(new, batch, tags, stats)
                    batch = []
            _store(new, batch, tags, stats)
    _finish(new, stats)
    return {k: stats[k] for k in ("total", "attached", "moved", "needs_attention")}


def _store(new: Document, batch: list, tags: dict, stats: dict) -> None:
    if not batch:
        return
    ops, ops_marks = [], []
    items = []
    for mark, decision in batch:
        if decision.fields is None:
            items.append(_item(new, mark, decision.reason or "not_found"))
            stats["needs_attention"] += 1
        else:
            ops.append(_op(new, mark, decision.fields, tags.get(mark.id, [])))
            ops_marks.append((mark, decision))
    if ops:
        result = annotations.apply_annotation_ops(new.user_id, new.id, ops)
        for (mark, decision), outcome in zip(ops_marks, result.results, strict=True):
            if outcome.status == "ok":
                stats[decision.outcome] += 1
            else:  # the plan's mark limit or a rule: the student still keeps the mark, as an item
                items.append(_item(new, mark, "invalid"))
                stats["needs_attention"] += 1
    ReanchorItem.objects.bulk_create(items, ignore_conflicts=True)


def _finish(new: Document, stats: dict, *, failed: bool = False) -> None:
    Document.objects.filter(pk=new.pk).update(
        reanchor_status="failed" if failed else "done", reanchor_stats=stats, updated_at=timezone.now()
    )
    if not failed:
        events.announce_reanchor_done(
            new.user_id,
            new.id,
            attached=stats["attached"] + stats["moved"],
            needs_attention=stats["needs_attention"],
        )


def give_up(payload: dict) -> None:
    """The queue gave up: the marks stay on the old edition and the new one says so."""
    Document.objects.filter(pk=payload.get("document_id"), reanchor_status__in=["waiting", "running"]).update(
        reanchor_status="failed", updated_at=timezone.now()
    )


# --- Needs attention ------------------------------------------------------------------------------------------------------
def _locked_item(user_id, document_id, item_id) -> tuple[Document, ReanchorItem]:
    document = documents.get_locked(user_id, document_id)
    item = ReanchorItem.objects.select_for_update().filter(pk=item_id, document=document, user_id=user_id).first()
    if item is None:
        raise NotFound("Mark not found.")
    return document, item


def _note_body(item: ReanchorItem, title: str) -> tuple[str, str]:
    heading = f"{title}, page {item.page}"
    parts = []
    if item.quote_exact:
        parts.append("\n".join(f"> {line}" for line in item.quote_exact.splitlines() if line.strip()))
    if item.comment.strip():
        parts.append(item.comment.strip())
    return heading[:200], "\n\n".join(parts)


@transaction.atomic
def resolve_item(user_id, document_id, item_id, *, action: str, page: int | None = None) -> ReanchorItem:
    """
    `keep`: put the mark on the new edition as it was (same shape, `page` or its old page) for the student to adjust.
    `note`: save its quote and comment as a note, filed under the document's chapter. `dismiss`: forget it.
    Repeating the same decision is fine; a different one after the first is 409 `already_resolved`.
    """
    document, item = _locked_item(user_id, document_id, item_id)
    wanted = {"keep": "kept", "note": "noted", "dismiss": "dismissed"}[action]
    if item.status != ReanchorItem.Status.OPEN:
        if item.status == wanted:
            return item
        raise AlreadyResolved
    if action == "keep":
        target = page or item.page
        if document.page_count and not 1 <= target <= document.page_count:
            raise PageOutOfRange
        mark_id = carried_id(document.id, item.source_annotation_id)
        fields = {
            "kind": item.kind,
            "page": target,
            "geometry": item.geometry,
            "color": item.color,
            "comment": item.comment,
            "quote_exact": item.quote_exact,
        }
        result = annotations.apply_annotation_ops(
            user_id, document.id, [annotations.AnnotationOp(op="upsert", id=mark_id, fields=fields)]
        )
        outcome = result.results[0]
        if outcome.status != "ok":
            raise outcome.error or PageOutOfRange
        item.new_annotation_id = mark_id
    elif action == "note":
        title, body = _note_body(item, document.title)
        if not body:
            raise NothingToSave
        created = note_services.create_note(
            user_id,
            client_id=uuid.uuid5(NAMESPACE, f"note:{item.id}"),
            title=title,
            body_md=body,
            chapter_id=document.chapter_id,
            topic_id=document.topic_id,
        )
        item.result_note_id = created.note.id
    item.status, item.resolved_at = wanted, timezone.now()
    item.save()
    return item
