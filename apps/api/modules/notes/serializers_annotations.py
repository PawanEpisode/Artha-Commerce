"""
Input validation and output shapes of the marks endpoints (contract "Annotations"). Output builders are plain functions over the
selectors' `AnnotationCard`, like `serializers.py`. A mark's text and quote only ever travel in these bodies.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError

from core.errors import CodedError
from core.recall_port import CARD_KINDS, get_recall_provider

from .errors import AnnotationConflict, BatchTooLarge
from .selectors import AnnotationCard
from .serializers import MARK_COLORS, link_dict, tag_dict
from .services.annotation_ops import EDITABLE, AnnotationOp, BatchResult, OpResult

MAX_BATCH = 100
KINDS = ["highlight", "underline", "ink", "textbox", "sticky", "bookmark", "area"]


# --- Input ----------------------------------------------------------------------------------------------------------------
class MarkFields(serializers.Serializer):
    """The fields of a mark. Only what the client sent reaches the service, so an omitted field is left alone."""

    kind = serializers.ChoiceField(choices=KINDS, required=False)
    page = serializers.IntegerField(min_value=1, max_value=5000, required=False)
    geometry = serializers.DictField(
        required=False
    )  # shape and size are `domain.geometry`'s call (422 invalid_geometry)
    color = serializers.ChoiceField(choices=MARK_COLORS, required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=2000, trim_whitespace=False)
    quote_exact = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=1000, trim_whitespace=False
    )
    quote_prefix = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=32, trim_whitespace=False
    )
    quote_suffix = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, max_length=32, trim_whitespace=False
    )
    text_start = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    text_end = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    anchor_engine = serializers.ChoiceField(choices=["pdfjs", "ocr"], required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    topic_id = serializers.UUIDField(required=False, allow_null=True)
    tag_ids = serializers.ListField(child=serializers.UUIDField(), required=False, max_length=20)
    device_id = serializers.CharField(required=False, allow_null=True, max_length=36)
    base_rev = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    base = serializers.DictField(required=False, child=serializers.JSONField())
    resolution = serializers.ChoiceField(choices=["mine", "theirs", "both"], required=False, allow_null=True)


class UpsertSerializer(MarkFields):
    """Body of `PUT annotations/{id}/` (the id is in the path)."""

    document_id = serializers.UUIDField()


class DeleteSerializer(serializers.Serializer):
    base_rev = serializers.IntegerField(min_value=0, required=False, allow_null=True)


class BatchSerializer(serializers.Serializer):
    """Only the envelope is validated here; each op is validated alone so one bad op never fails the rest (`parse_op`)."""

    document_id = serializers.UUIDField()
    ops = serializers.ListField(child=serializers.DictField(), allow_empty=True)

    def validate_ops(self, ops):
        if len(ops) > MAX_BATCH:
            raise BatchTooLarge
        return ops


class BatchOpSerializer(MarkFields):
    op = serializers.ChoiceField(choices=["upsert", "delete", "restore"])
    id = serializers.UUIDField()
    document_id = serializers.UUIDField(required=False)


class CardSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=list(CARD_KINDS), required=False, allow_null=True)


class DeltaQuery(serializers.Serializer):
    since_seq = serializers.IntegerField(min_value=0, required=False, default=0)
    limit = serializers.IntegerField(min_value=1, max_value=500, required=False, default=500)


def to_op(op: str, mark_id, data: Mapping[str, Any]) -> AnnotationOp:
    """An `AnnotationOp` from validated data: the mark fields the client sent, plus the sync fields."""
    fields = {k: data[k] for k in ("kind", *EDITABLE) if k in data}
    return AnnotationOp(
        op=op,
        id=mark_id,
        base_rev=data.get("base_rev"),
        base=data.get("base") or {},
        fields=fields,
        tag_ids=data.get("tag_ids"),
        device_id=data.get("device_id"),
        resolution=data.get("resolution"),
    )


def parse_op(raw: Mapping[str, Any], document_id) -> tuple[AnnotationOp | None, OpResult | None]:
    """`(op, None)` for a valid batch op, `(None, rejected result)` for an invalid one, so the rest of the batch still runs."""
    s = BatchOpSerializer(data=raw)
    if not s.is_valid():
        mark_id = raw.get("id") if isinstance(raw, Mapping) else None
        return None, OpResult(mark_id, "rejected", error=ValidationError(s.errors))
    d = s.validated_data
    if d.get("document_id") not in (None, document_id):
        return None, OpResult(
            d["id"], "rejected", error=ValidationError({"document_id": "Must be the batch's document."})
        )
    return to_op(d["op"], d["id"], d), None


# --- Output ---------------------------------------------------------------------------------------------------------------
def annotation_dict(card: AnnotationCard, *, recall: bool | None = None) -> dict:
    """The `Annotation` shape. `recall_card_id` is null while no recall provider is registered (the card is not reachable)."""
    a = card.annotation
    show_card = (get_recall_provider() is not None) if recall is None else recall
    return {
        "id": a.id,
        "document_id": a.document_id,
        "page": a.page,
        "kind": a.kind,
        "geometry": a.geometry,
        "color": a.color,
        "comment": a.comment,
        "quote_exact": a.quote_exact,
        "quote_prefix": a.quote_prefix,
        "quote_suffix": a.quote_suffix,
        "text_start": a.text_start,
        "text_end": a.text_end,
        "anchor_engine": a.anchor_engine,
        "link": link_dict(card.link),
        "chapter_source": a.chapter_source,
        "tags": [tag_dict(t) for t in card.tags],
        "recall_card_id": a.recall_card_id if show_card else None,
        "rev": a.rev,
        "seq": a.seq,
        "device_id": a.device_id,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
        "deleted_at": a.deleted_at,
    }


def error_body(exc: Exception, cards: Mapping[Any, AnnotationCard] | None = None) -> dict:
    """`{code, message, details}` for a failed op, the same content the error envelope carries for a single request."""
    if isinstance(exc, AnnotationConflict):
        theirs = (cards or {}).get(exc.theirs.id)
        return {
            "code": exc.default_code,
            "message": str(exc.detail),
            "details": {
                "mine": exc.mine,
                "theirs": annotation_dict(theirs) if theirs else None,
                "device_label": (exc.theirs.device_id or "")[:8] or None,
                "theirs_updated_at": exc.theirs.updated_at,
            },
        }
    if isinstance(exc, ValidationError):
        return {"code": "validation_error", "message": "Some fields are not valid.", "details": exc.detail}
    extra = getattr(exc, "extra", None) if isinstance(exc, CodedError) else None
    code = getattr(exc, "default_code", "error")
    return {
        "code": code,
        "message": str(exc.detail) if isinstance(exc, APIException) else "Request failed.",
        "details": extra,
    }


def _rows_of(results: Iterable[OpResult]) -> list:
    return [r.annotation for r in results if r.annotation is not None]


def marks_dict(batch: BatchResult) -> dict:
    """The quiet limit notice: `near_limit` from 95% of the plan's marks per document."""
    return {"count": batch.marks_count, "limit": batch.marks_limit, "near_limit": batch.near_limit}


def result_dict(r: OpResult, cards: Mapping[Any, AnnotationCard]) -> dict:
    out: dict[str, Any] = {"id": r.id, "status": r.status}
    if r.status == "ok":
        out |= {
            "annotation": annotation_dict(cards[r.annotation.id]),
            "merged": r.merged,
            "restored": r.restored,
            "overwritten": r.overwritten,
            "edit_wins": r.edit_wins,
        }
    else:
        out["error"] = error_body(r.error, cards)
    return out


def batch_dict(batch: BatchResult, cards: Mapping[Any, AnnotationCard]) -> dict:
    return {
        "results": [result_dict(r, cards) for r in batch.results],
        "change_seq": batch.change_seq,
        "marks": marks_dict(batch),
    }


def single_dict(r: OpResult, batch: BatchResult, card: AnnotationCard) -> dict:
    """`PUT`, `DELETE` and `restore` bodies: `{annotation, merged, restored, overwritten}` (+ `edit_wins` for DELETE) plus the notice."""
    return {
        "annotation": annotation_dict(card),
        "merged": r.merged,
        "restored": r.restored,
        "overwritten": r.overwritten,
        "edit_wins": r.edit_wins,
        "change_seq": batch.change_seq,
        "marks": marks_dict(batch),
    }


def delta_dict(delta) -> dict:
    return {
        "items": [annotation_dict(c) for c in delta.items],
        "change_seq": delta.change_seq,
        "next_since_seq": delta.next_since_seq,
        "has_more": delta.has_more,
    }


def cards_by_id(results: Iterable[OpResult]) -> dict:
    from .selectors import annotation_cards

    return {c.annotation.id: c for c in annotation_cards(_rows_of(results))}
