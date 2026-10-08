"""Input and output shapes of Replace edition (contract R3)."""

from __future__ import annotations

from rest_framework import serializers

from .selectors.reanchor import Attention
from .serializers_documents import MAX_NAME
from .services.reanchor import ACTIONS


class ReplaceBody(serializers.Serializer):
    client_id = serializers.UUIDField()
    filename = serializers.CharField(max_length=MAX_NAME, trim_whitespace=True)
    bytes = serializers.IntegerField(min_value=1, max_value=2**40)
    mime = serializers.CharField(max_length=100)
    page_count_hint = serializers.IntegerField(
        min_value=1, max_value=1_000_000, required=False, allow_null=True, default=None
    )
    edition_label = serializers.CharField(max_length=40, required=False, allow_blank=True, default="")


class AttentionQuery(serializers.Serializer):
    status = serializers.ChoiceField(choices=["open", "kept", "noted", "dismissed"], required=False)


class ResolveBody(serializers.Serializer):
    action = serializers.ChoiceField(choices=list(ACTIONS))
    page = serializers.IntegerField(min_value=1, max_value=1_000_000, required=False, allow_null=True, default=None)


def item_out(i) -> dict:
    return {
        "id": i.id,
        "source_annotation_id": i.source_annotation_id,
        "kind": i.kind,
        "page": i.page,
        "color": i.color,
        "quote": i.quote_exact,
        "comment": i.comment,
        "reason": i.reason,
        "status": i.status,
        "new_annotation_id": i.new_annotation_id,
        "result_note_id": i.result_note_id,
        "resolved_at": i.resolved_at,
    }


def attention_out(a: Attention) -> dict:
    d = a.document
    return {
        "document_id": d.id,
        "replaces_document_id": d.replaces_document_id,
        "status": d.reanchor_status,
        "stats": d.reanchor_stats,
        "items": [item_out(i) for i in a.items],
    }


class UnlockBody(serializers.Serializer):
    # Kept exactly as typed: no trimming, because a password may begin or end with a space.
    password = serializers.CharField(
        max_length=256, trim_whitespace=False, write_only=True, style={"input_type": "password"}
    )


class PartNumbers(serializers.Serializer):
    numbers = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=10_000), min_length=1, max_length=20
    )


class FinishBody(serializers.Serializer):
    """The part numbers the browser sent. Sizes and ETags come from storage, not from the browser."""

    parts = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=10_000), min_length=1, max_length=10_000
    )
