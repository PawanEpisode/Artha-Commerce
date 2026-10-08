"""Small builders for the schema and service tests. They write rows directly; the services arrive in later waves."""

from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

from django.utils import timezone

from modules.recall.models import RecallCard, RecallDeck, RecallItem, RecallItemVersion

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
OTHER = uuid.UUID("9a1d2c3b-4e5f-4a6b-8c7d-0e1f2a3b4c5d")


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def make_item(owner=USER, *, text="What is X?", kind="pointer", **extra) -> RecallItem:
    fields = {"ownership": "user", "owner_user_id": owner} if owner else {"ownership": "platform"}
    item = RecallItem.objects.create(
        kind=kind, fingerprint=fingerprint(text + str(uuid.uuid4())), **{**fields, **extra}
    )
    version = RecallItemVersion.objects.create(
        item=item,
        version_no=1,
        state="live",
        fields={"v": 1, "prompt_md": text, "answer_md": "Y"},
        content_hash=fingerprint(text),
        plain_text=text,
    )
    RecallItem.objects.filter(pk=item.pk).update(live_version=version, current_version=version)
    item.refresh_from_db()
    return item


def make_deck(owner=USER, **extra) -> RecallDeck:
    kind = "user" if owner else "platform"
    return RecallDeck.objects.create(kind=kind, owner_user_id=owner, title="A deck", **extra)


def make_card(item: RecallItem | None = None, owner=USER, **extra) -> RecallCard:
    item = item or make_item(owner)
    return RecallCard.objects.create(user_id=owner, item=item, item_version=item.live_version, **extra)


def reviewed_fields(days: float = 3.0) -> dict:
    """The columns of a card that has been reviewed once (state 2)."""
    now = timezone.now()
    return {
        "state": 2,
        "stability": 2.3,
        "difficulty": 5.0,
        "due_scheduled_at": now + timedelta(days=days),
        "due_at": now + timedelta(days=days),
        "last_review_at": now,
        "reps": 1,
    }
