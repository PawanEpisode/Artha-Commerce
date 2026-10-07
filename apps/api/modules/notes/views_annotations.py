"""
Thin views for the marks endpoints (contract "Annotations"): auth, both flags, parse, call the service or selector, serialise.
Every mark route answers 404 for a document or mark the caller does not own, and a mark id owned by someone else is
indistinguishable from one that does not exist.
"""

from __future__ import annotations

from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from . import selectors, services
from . import serializers_annotations as ser
from .services.annotation_ops import OpResult
from .views import PdfView, PdfWriteView


def _only(batch) -> OpResult:
    """The one result of a single-op request. A failed op is raised so the usual error envelope answers (409, 422, 429, 404)."""
    result = batch.results[0]
    if result.status == "ok":
        return result
    if result.status == "conflict":
        card = selectors.get_annotation(result.annotation.user_id, result.annotation.id)
        result.error.extra = ser.error_body(result.error, {card.annotation.id: card})["details"]
    raise result.error


def _single(request, document_id, op) -> Response:
    batch = services.apply_annotation_ops(request.user.id, document_id, [op])
    result = _only(batch)
    card = selectors.get_annotation(request.user.id, result.annotation.id)
    return Response(ser.single_dict(result, batch, card), status=201 if result.created else 200)


def _document_of(user_id, mark_id):
    document_id = selectors.annotation_document_id(user_id, mark_id)
    if document_id is None:
        raise NotFound("Mark not found.")
    return document_id


class DocumentAnnotationsView(PdfView):
    """`GET documents/{id}/annotations/`: the delta feed (tombstones included, ordered by `seq`)."""

    def get(self, request, document_id):
        d = self.parse(ser.DeltaQuery, request.query_params).validated_data
        delta = selectors.delta_annotations(request.user.id, document_id, since_seq=d["since_seq"], limit=d["limit"])
        if delta is None:
            raise NotFound("Document not found.")
        return Response(ser.delta_dict(delta))


class AnnotationDetailView(PdfWriteView):
    def put(self, request, annotation_id):
        s = self.parse(ser.UpsertSerializer, request.data)
        d = s.validated_data
        return _single(request, d["document_id"], ser.to_op("upsert", annotation_id, d))

    def delete(self, request, annotation_id):
        d = self.parse(ser.DeleteSerializer, request.data or {}).validated_data
        op = ser.to_op("delete", annotation_id, d)
        return _single(request, _document_of(request.user.id, annotation_id), op)


class AnnotationRestoreView(PdfWriteView):
    def post(self, request, annotation_id):
        op = ser.to_op("restore", annotation_id, {})
        return _single(request, _document_of(request.user.id, annotation_id), op)


class AnnotationBatchView(PdfWriteView):
    """`POST annotations/batch/`: up to 100 ops in order under one document lock; a failed op never aborts the rest."""

    def post(self, request):
        d = self.parse(ser.BatchSerializer, request.data).validated_data
        parsed = [ser.parse_op(raw, d["document_id"]) for raw in d["ops"]]
        runnable = [op for op, _ in parsed if op is not None]
        batch = services.apply_annotation_ops(request.user.id, d["document_id"], runnable)
        done = iter(batch.results)
        batch.results = [rejected if op is None else next(done) for op, rejected in parsed]  # the client's order
        return Response(ser.batch_dict(batch, ser.cards_by_id(batch.results)))


class AnnotationCardView(PdfWriteView):
    """`POST annotations/{id}/card/`: "Make a card" from a mark. 503 `recall_unavailable` until a recall provider registers."""

    def post(self, request, annotation_id):
        d = self.parse(ser.CardSerializer, request.data).validated_data
        result = services.create_recall_card(
            request.user.id, item_type="annotation", item_id=annotation_id, kind=d.get("kind"), client_id=d["client_id"]
        )
        return Response({"card_id": result.card_id, "existing": result.existing})
