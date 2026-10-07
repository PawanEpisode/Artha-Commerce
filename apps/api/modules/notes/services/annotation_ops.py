"""
Writing marks (ERD 3.2, 3.6, Q-8, Q-9): `apply_annotation_ops` takes ONE `FOR UPDATE` lock on the document row per call, applies
the ops in order and releases it at commit. Under that lock `change_seq` goes up by exactly one per accepted write (no gaps, no
two marks with the same `seq`) and `marks_count` is adjusted in the same transaction, so the delta feed and the counter can
never disagree. The lock is also what makes "last write wins" mean arrival order at the database, not clock time.

An op never aborts its neighbours: each runs in a savepoint and ends as `ok`, `conflict` (an overlapping comment edit,
nothing written) or `rejected` (a rule broke: geometry, quota, unknown chapter or tag, a mark that is not the student's).
The pure rules (what a field merge accepts, edit versus delete, which chapter a mark inherits) live in `domain/`; this
module only loads rows and carries the decision out. Mark text never goes to logs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError

from core.errors import CodedError

from .. import events
from ..domain import merge
from ..domain.chapter_inheritance import effective_link
from ..domain.geometry import MAX_BYTES, serialised_size, validate_geometry
from ..errors import AnnotationConflict, InvalidGeometry, InvalidMark, QuotaExceeded
from ..models import Annotation, Document, DocumentChapter, ItemTag
from . import links, quota, search_index, tags

TRASH_DAYS = 30
MAX_MARKS_HARD = 20_000  # the database check on `notes_document.marks_count`
NEAR_LIMIT_PERCENT = 95  # the client shows a quiet notice from here
MAX_PAGE = 5000
COUNTED_KINDS = frozenset(Annotation.LISTED_KINDS)  # kinds that announce chapter counts (FR-F03-30)
# fields a write may carry, and the ones compared field by field (`chapter_id` and `topic_id` are links, handled apart)
SCALARS = ("page", "color", "quote_exact", "quote_prefix", "quote_suffix", "text_start", "text_end", "anchor_engine")
EDITABLE = (*SCALARS, "comment", "geometry", "chapter_id", "topic_id")
RESOLUTIONS = ("mine", "theirs", "both")


def _now():
    return timezone.now()


@dataclass(frozen=True)
class AnnotationOp:
    """One change. `fields` holds only what the client sent; `tag_ids` None means "leave the tags alone"."""

    op: str  # upsert | delete | restore
    id: UUID
    base_rev: int | None = None
    base: Mapping[str, Any] = field(default_factory=dict)
    fields: Mapping[str, Any] = field(default_factory=dict)
    tag_ids: Sequence[UUID] | None = None
    device_id: str | None = None
    resolution: str | None = None


@dataclass
class OpResult:
    id: UUID
    status: str  # ok | conflict | rejected
    annotation: Annotation | None = None
    created: bool = False
    merged: bool = False
    restored: bool = False
    overwritten: list[str] = field(default_factory=list)
    edit_wins: bool = False
    error: Exception | None = None


@dataclass
class BatchResult:
    results: list[OpResult]
    change_seq: int
    marks_count: int
    marks_limit: int

    @property
    def near_limit(self) -> bool:
        return self.marks_count * 100 >= self.marks_limit * NEAR_LIMIT_PERCENT


class _Ctx:
    """What one locked batch shares: the document, the running counters and what to announce at the end."""

    def __init__(self, user_id, doc: Document):
        self.user_id, self.doc = user_id, doc
        self.seq, self.count = doc.change_seq, doc.marks_count
        self.limit = min(quota.max_marks_per_document(user_id), MAX_MARKS_HARD)
        self.announce: list[tuple[str, tuple]] = []  # (reason, link key)
        self._ranges: list[dict] | None = None
        self._links: dict[tuple, dict] = {}

    def snapshot(self) -> tuple[int, int, int]:
        return self.seq, self.count, len(self.announce)

    def restore(self, snap: tuple[int, int, int]) -> None:
        self.seq, self.count = snap[0], snap[1]
        del self.announce[snap[2] :]

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    def link(self, chapter_id, topic_id) -> dict:
        key = (chapter_id, topic_id)
        if key not in self._links:
            self._links[key] = links.link_columns(chapter_id, topic_id)
        return dict(self._links[key])

    def ranges(self) -> list[dict]:
        if self._ranges is None:
            rows = DocumentChapter.objects.filter(document_id=self.doc.id).order_by("page_from")
            self._ranges = [
                {"page_from": r.page_from, "page_to": r.page_to, "chapter": (r.chapter_id, r.topic_id)} for r in rows
            ]
        return self._ranges

    def reserve_slot(self) -> None:
        if self.count + 1 > self.limit:
            raise QuotaExceeded(
                extra={
                    "kind": "marks",
                    "used": self.count,
                    "limit": self.limit,
                    "plan": quota.plan_code_for(self.user_id),
                }
            )
        self.count += 1

    def release_slot(self) -> None:
        self.count = max(self.count - 1, 0)

    def say(self, reason: str, *keys: tuple | None) -> None:
        self.announce += [(reason, k) for k in keys if k]


def lock_document(user_id, document_id) -> Document:
    doc = Document.objects.select_for_update().filter(pk=document_id, user_id=user_id).first()
    if doc is None:
        raise NotFound("Document not found.")
    return doc


# --- Entry point ---------------------------------------------------------------------------------------------------------
@transaction.atomic
def apply_annotation_ops(user_id, document_id, ops: Sequence[AnnotationOp]) -> BatchResult:
    """
    Apply `ops` to one document of the student, in order, under one lock. `NotFound` when the document is not theirs.
    Per-op failures are results, never exceptions (see the module docstring).
    """
    doc = lock_document(user_id, document_id)
    ctx = _Ctx(user_id, doc)
    rows = {a.id: a for a in Annotation.objects.filter(pk__in=[o.id for o in ops])}
    results: list[OpResult] = []
    for op in ops:
        snap = ctx.snapshot()
        try:
            with transaction.atomic():
                results.append(_apply(ctx, rows, op))
        except AnnotationConflict as exc:
            ctx.restore(snap)
            results.append(OpResult(op.id, "conflict", annotation=exc.theirs, error=exc))
        except (CodedError, NotFound, ValidationError) as exc:
            ctx.restore(snap)
            results.append(OpResult(op.id, "rejected", error=exc))
        except (
            IntegrityError
        ):  # the id was taken by someone else between our read and our insert: same answer as a foreign id
            ctx.restore(snap)
            results.append(OpResult(op.id, "rejected", error=NotFound("Mark not found.")))
    if ctx.seq != doc.change_seq or ctx.count != doc.marks_count:
        Document.objects.filter(pk=doc.pk).update(change_seq=ctx.seq, marks_count=ctx.count)
    for reason in dict.fromkeys(r for r, _ in ctx.announce):
        events.announce_counts(user_id, [k for r, k in ctx.announce if r == reason], reason)
    return BatchResult(results, ctx.seq, ctx.count, ctx.limit)


def _apply(ctx: _Ctx, rows: dict[UUID, Annotation], op: AnnotationOp) -> OpResult:
    row = rows.get(op.id)
    if row is not None and (str(row.user_id) != str(ctx.user_id) or row.document_id != ctx.doc.id):
        raise NotFound("Mark not found.")  # someone else's id, or another document: never a hint
    if op.op == "upsert":
        if row is None:
            if op.base_rev:  # an edit of a mark that is gone (purged): nothing to edit
                raise NotFound("Mark not found.")
            result = _create(ctx, op)
            rows[op.id] = result.annotation
            return result
        if not op.base_rev:  # a replayed create: the stored row is the answer
            return OpResult(op.id, "ok", annotation=row)
        return _edit(ctx, row, op)
    if row is None:
        raise NotFound("Mark not found.")
    return _delete(ctx, row, op) if op.op == "delete" else _restore(ctx, row, op)


# --- Pieces shared by create and edit -------------------------------------------------------------------------------------
def _check_page(ctx: _Ctx, page: int) -> None:
    pages = ctx.doc.page_count
    if not 1 <= page <= MAX_PAGE or (pages and page > pages):
        raise InvalidMark("That page is not in this document.")


def _normalised_geometry(kind: str, geometry: Any) -> dict:
    checked = validate_geometry(kind, geometry)
    if checked["errors"]:
        raise InvalidGeometry(extra={"errors": checked["errors"]})
    if serialised_size(checked["geometry"]) > MAX_BYTES:
        raise InvalidGeometry(extra={"errors": [{"code": "too_large", "message": "This shape is too large."}]})
    return checked["geometry"]


def _as_id(value) -> str | None:
    return None if value is None else str(value)


def _as_uuid(value) -> UUID | None:
    return None if value is None else UUID(str(value))


def _links_for(ctx: _Ctx, *, page: int, chapter_id, topic_id) -> tuple[dict, str]:
    """Link columns and `chapter_source` for a mark: explicit when the student chose, else range, document default, none."""
    explicit = (_as_uuid(chapter_id), _as_uuid(topic_id)) if (chapter_id or topic_id) else None
    default = (ctx.doc.chapter_id, ctx.doc.topic_id) if ctx.doc.chapter_id else None
    ref, source = effective_link(page, explicit, ctx.ranges() if explicit is None else [], default)
    return (ctx.link(*ref) if ref else links.link_columns(None)), source


def _counts_key(row: Annotation):
    return row.link_key() if row.kind in COUNTED_KINDS else None


# --- Create ---------------------------------------------------------------------------------------------------------------
def _create(ctx: _Ctx, op: AnnotationOp) -> OpResult:
    f = op.fields
    missing = [k for k in ("kind", "page", "geometry") if f.get(k) is None]
    if missing:
        raise ValidationError({k: "This field is required to create a mark." for k in missing})
    kind, page = f["kind"], f["page"]
    _check_page(ctx, page)
    geometry = _normalised_geometry(kind, f["geometry"])
    cols, source = _links_for(ctx, page=page, chapter_id=f.get("chapter_id"), topic_id=f.get("topic_id"))
    if op.tag_ids:
        tags.owned_tags(ctx.user_id, op.tag_ids)  # refuse before anything is written
    ctx.reserve_slot()
    row = Annotation(
        id=op.id,
        user_id=ctx.user_id,
        document=ctx.doc,
        kind=kind,
        page=page,
        geometry=geometry,
        comment=f.get("comment") or "",
        chapter_source=source,
        rev=1,
        seq=ctx.next_seq(),
        device_id=op.device_id,
        **{k: f.get(k) for k in ("color", "quote_exact", "quote_prefix", "quote_suffix", "text_start", "text_end")},
        anchor_engine=f.get("anchor_engine"),
        **cols,
    )
    row.save(force_insert=True)
    if op.tag_ids:
        tags.set_annotation_tags(ctx.user_id, row, op.tag_ids)
    search_index.refresh_annotation(row)
    ctx.say("created", _counts_key(row))
    return OpResult(op.id, "ok", annotation=row, created=True)


# --- Edit -----------------------------------------------------------------------------------------------------------------
def _stored_view(row: Annotation) -> dict[str, Any]:
    """The row in the form clients send fields (ids as strings), for the field-level compare."""
    return {
        **{k: getattr(row, k) for k in (*SCALARS, "comment", "geometry")},
        "chapter_id": _as_id(row.chapter_id),
        "topic_id": _as_id(row.topic_id),
    }


def _incoming(row: Annotation, op: AnnotationOp) -> dict[str, Any]:
    f = op.fields
    if "kind" in f and f["kind"] != row.kind:
        raise InvalidMark("A mark cannot change its kind.")
    out = {k: (_as_id(f[k]) if k in ("chapter_id", "topic_id") else f[k]) for k in EDITABLE if k in f}
    if "page" in out and out["page"] is None:
        raise ValidationError({"page": "A mark needs a page."})
    if "geometry" in out:
        out["geometry"] = _normalised_geometry(row.kind, out["geometry"])
    return out


def _edit(ctx: _Ctx, row: Annotation, op: AnnotationOp) -> OpResult:
    stored, incoming = _stored_view(row), _incoming(row, op)
    if "page" in incoming:
        _check_page(ctx, incoming["page"])
    decided: dict[str, Any] = {}
    if op.resolution and "comment" in incoming and incoming["comment"] != stored["comment"]:
        # the student settled a parked conflict: mine, theirs or both, whatever the other device has done since
        decided["comment"] = merge.resolve_conflict(op.resolution, incoming.pop("comment"), stored["comment"])
    decision = merge.resolve_edit_vs_delete(
        stored_deleted=row.deleted_at is not None, stored_rev=row.rev, base_rev=op.base_rev or 0, op="edit"
    )
    if op.base_rev >= row.rev:  # nobody wrote in between: take every field
        accepted, overwritten = dict(incoming), []
    else:
        outcome = merge.reconcile_fields(stored, op.base, incoming)
        if outcome["conflict"]:
            raise AnnotationConflict(row, {k: v for k, v in incoming.items() if k != "geometry"})
        accepted, overwritten = outcome["accepted"], outcome["overwritten"]
    accepted |= decided
    merged = "comment" in incoming and "comment" in accepted and accepted["comment"] != incoming["comment"]

    restoring = decision["action"] == "restore"
    changes = {k: v for k, v in accepted.items() if k not in ("chapter_id", "topic_id") and stored[k] != v}
    cols, source = _relinked(ctx, row, accepted, incoming, changes)
    link_changed = cols is not None and (
        source != row.chapter_source
        or any(cols[k] != getattr(row, k) for k in ("chapter_id", "topic_id", "level_id", "subject_key", "chapter_key"))
    )
    if op.tag_ids is not None:
        tags.owned_tags(ctx.user_id, op.tag_ids)
    tags_changed = op.tag_ids is not None and _tags_differ(row, op.tag_ids)
    if not (changes or link_changed or tags_changed or restoring):
        return OpResult(op.id, "ok", annotation=row)  # a replay: everything it says is already stored

    before = _counts_key(row)
    if restoring:
        ctx.reserve_slot()
        row.deleted_at = row.purge_after = None
    for k, v in changes.items():
        setattr(row, k, v)
    if link_changed:
        for k, v in cols.items():
            setattr(row, k, v)
        row.chapter_source = source
    if op.device_id:
        row.device_id = op.device_id
    row.rev += 1
    row.seq = ctx.next_seq()
    row.save()
    if tags_changed:
        tags.set_annotation_tags(ctx.user_id, row, op.tag_ids)
    if "comment" in changes or "quote_exact" in changes:
        search_index.refresh_annotation(row)
    after = _counts_key(row)
    if restoring:
        ctx.say("restored", after)
    elif before != after:
        ctx.say("relinked", before, after)
    return OpResult(op.id, "ok", annotation=row, merged=merged, restored=restoring, overwritten=overwritten)


def _relinked(ctx: _Ctx, row: Annotation, accepted: dict, incoming: dict, changes: dict) -> tuple[dict | None, str]:
    """New link columns and source when the write touches the chapter, the topic or (for an inherited link) the page."""
    chose = "chapter_id" in incoming or "topic_id" in incoming
    moved = "page" in changes and row.chapter_source != "explicit"
    if not (chose or moved):
        return None, row.chapter_source
    explicit = row.chapter_source == "explicit"
    chapter = accepted["chapter_id"] if "chapter_id" in accepted else (_as_id(row.chapter_id) if explicit else None)
    topic = accepted["topic_id"] if "topic_id" in accepted else (_as_id(row.topic_id) if explicit else None)
    return _links_for(ctx, page=accepted.get("page", row.page), chapter_id=chapter, topic_id=topic)


def _tags_differ(row: Annotation, tag_ids: Sequence[UUID]) -> bool:
    have = set(ItemTag.objects.filter(annotation=row).values_list("tag_id", flat=True))
    return have != {UUID(str(t)) for t in tag_ids}


# --- Delete and restore ---------------------------------------------------------------------------------------------------
def _delete(ctx: _Ctx, row: Annotation, op: AnnotationOp) -> OpResult:
    decision = merge.resolve_edit_vs_delete(
        stored_deleted=row.deleted_at is not None,
        stored_rev=row.rev,
        base_rev=row.rev if op.base_rev is None else op.base_rev,
        op="delete",
    )
    if decision["action"] == "noop":
        return OpResult(op.id, "ok", annotation=row)
    if decision["action"] == "keep":  # edited elsewhere since: the edit wins, nothing is lost
        return OpResult(op.id, "ok", annotation=row, edit_wins=True)
    now = _now()
    row.deleted_at, row.purge_after = now, now + timedelta(days=TRASH_DAYS)
    row.rev += 1
    row.seq = ctx.next_seq()
    row.save()
    ctx.release_slot()
    ctx.say("trashed", _counts_key(row))
    return OpResult(op.id, "ok", annotation=row)


def _restore(ctx: _Ctx, row: Annotation, op: AnnotationOp) -> OpResult:
    if row.deleted_at is None:
        return OpResult(op.id, "ok", annotation=row)
    ctx.reserve_slot()
    row.deleted_at = row.purge_after = None
    if row.chapter_source != "explicit":  # ranges may have moved while it sat in the trash
        cols, source = _links_for(ctx, page=row.page, chapter_id=None, topic_id=None)
        for k, v in cols.items():
            setattr(row, k, v)
        row.chapter_source = source
    row.rev += 1
    row.seq = ctx.next_seq()
    row.save()
    ctx.say("restored", _counts_key(row))
    return OpResult(op.id, "ok", annotation=row, restored=True)
