"""Reads for Replace edition: the "Needs attention" list of a new edition. Always scoped to the student (None for anyone else's)."""

from __future__ import annotations

from dataclasses import dataclass

from ..models import Document, ReanchorItem


@dataclass(frozen=True)
class Attention:
    document: Document
    items: tuple[ReanchorItem, ...]


def get_attention(user_id, document_id, *, status: str | None = None) -> Attention | None:
    document = Document.objects.filter(pk=document_id, user_id=user_id).first()
    if document is None:
        return None
    items = ReanchorItem.objects.filter(document=document, user_id=user_id)
    if status:
        items = items.filter(status=status)
    return Attention(document, tuple(items.order_by("page", "created_at", "id")))
