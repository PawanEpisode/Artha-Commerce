"""Helpers shared by the card tests: build requests, create through the API, read rows back."""

from __future__ import annotations

import uuid

from modules.recall.models import RecallCard, RecallQuotaUsage

POINTER = {"prompt_md": "When is ITC blocked?", "answer_md": "Under section 17(5)."}


def new(api, fields=None, kind="pointer", **extra):
    body = {"client_id": str(uuid.uuid4()), "kind": kind, "fields": fields or dict(POINTER), **extra}
    return api.post("/recall/cards/", body)


def made(api, fields=None, kind="pointer", **extra) -> dict:
    """Create one card and return its first card payload."""
    res = new(api, fields, kind, **extra)
    assert res.status_code == 201, res.json_body
    return res.json_body["cards"][0]


def used(user_id) -> int:
    return RecallQuotaUsage.objects.filter(pk=user_id).values_list("cards_active", flat=True).first() or 0


def row(card_id) -> RecallCard:
    return RecallCard.objects.select_related("item", "item_version").get(pk=card_id)


def distinct(n: int, prefix: str = "Question") -> list[dict]:
    return [{"prompt_md": f"{prefix} number {i}?", "answer_md": f"Answer {i}"} for i in range(n)]
