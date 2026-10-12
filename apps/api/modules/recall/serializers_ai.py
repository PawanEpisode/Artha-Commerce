"""Input parsing and output shapes of the AI suggestion endpoints. Draft text leaves only in a response body, never in a log."""

from __future__ import annotations

from rest_framework import serializers

from . import registry
from .domain import suggestions as sdomain
from .models import ITEM_KINDS
from .selectors.suggestions import BatchView


class SuggestionRequestSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    chapter_id = serializers.UUIDField()
    sources = serializers.ListField(
        child=serializers.ChoiceField(choices=sdomain.SOURCE_KINDS), min_length=1, max_length=len(sdomain.SOURCE_KINDS)
    )
    pasted_text = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=sdomain.MAX_PASTED_CHARS, trim_whitespace=False
    )
    count = serializers.IntegerField(
        required=False, default=sdomain.DEFAULT_COUNT, min_value=sdomain.MIN_COUNT, max_value=sdomain.MAX_COUNT
    )
    kinds = serializers.ListField(
        child=serializers.ChoiceField(choices=ITEM_KINDS), required=False, default=list, max_length=7
    )


class BatchListQuery(serializers.Serializer):
    chapter_id = serializers.UUIDField(required=False)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=20)


class ConsentSerializer(serializers.Serializer):
    version = serializers.CharField(max_length=16)


class AcceptSerializer(serializers.Serializer):
    fields = serializers.DictField(child=serializers.CharField(allow_blank=True, trim_whitespace=False), required=False)
    force = serializers.BooleanField(required=False, default=False)


_SOURCE_LABELS = {
    "note": "Your note",
    "mark": "Your highlight",
    "question": "A question you got wrong",
    "pasted": "Text you pasted",
}


def evidence_label(ref: str) -> str:
    return _SOURCE_LABELS.get(ref.split(":", 1)[0], "Your material")


def suggestion_dict(s) -> dict:
    spec = registry.get_kind(s.kind)
    ordinals = spec.ordinals(s.fields) or [0]
    front, back = spec.render(s.fields, ordinals[0])
    return {
        "id": str(s.id),
        "position": s.position,
        "kind": s.kind,
        "fields": s.fields,
        "front_md": front,
        "back_md": back,
        "evidence_quote": s.evidence_quote,
        "evidence_label": evidence_label(s.evidence_source),
        "status": s.status,
        "item_id": str(s.item_id) if s.item_id else None,
        "decided_at": s.decided_at,
    }


def batch_dict(view: BatchView, *, estimate_seconds: int | None = None, reused: str | None = None) -> dict:
    b = view.batch
    return {
        "id": str(b.id),
        "status": b.status,
        "chapter_id": str(b.chapter_id),
        "sources": b.sources,
        "kinds": b.kinds,
        "requested_count": b.requested_count,
        "produced": b.produced,
        "dropped": b.dropped,
        "error_code": b.error_code or None,
        "created_at": b.created_at,
        "finished_at": b.finished_at,
        "expires_at": b.expires_at,
        "estimate_seconds": estimate_seconds,
        "reused": reused,
        "suggestions": [suggestion_dict(s) for s in view.suggestions],
    }
