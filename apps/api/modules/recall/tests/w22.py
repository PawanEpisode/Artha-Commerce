"""Builders for the living-deck tests (R2-W2): a second deck version with one change of each kind, and students who study the deck."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.utils import timezone

from modules.coverage.tests.conftest import USER as ME
from modules.recall.models import RecallCard, RecallDeckVersion, RecallDeckVersionItem, RecallSubscription
from modules.recall.services import decks as deck_service
from modules.recall.services import subscriptions

from .w11 import EDITOR, platform_item, published_deck


def pointer(text: str, answer: str = "Answer") -> dict:
    return {"prompt_md": text, "answer_md": answer}


def edit(item, fields: dict, kind: str):
    """A new draft item version of a platform item, with this change kind."""
    return deck_service.new_item_version(EDITOR, item, fields, change_kind=kind)


def publish_next(deck, *, edited=(), added=(), removed=(), changelog="Changes."):
    """
    A new live deck version: the items edited so far (their drafts are picked up), plus `added`, minus `removed`. Returns the version.
    `edited` is only there for readability: `start_draft_version` copies the live rows pointing at each item's newest version.
    """
    draft = deck_service.start_draft_version(EDITOR, deck)
    rows = list(RecallDeckVersionItem.objects.filter(deck_version=draft).select_related("item").order_by("position"))
    keep = [r.item for r in rows if r.item_id not in {i.id for i in removed}] + list(added)
    deck_service.set_draft_rows(draft, [(i, None) for i in keep])
    return deck_service.publish_deck_version(EDITOR, deck.id, draft.id, changelog_md=changelog)


def deck_with_student(n=4, *, user=ME, **kw):
    """A published deck (version 1) of `n` pointer items and a student subscribed to it. Returns (deck, items, subscription)."""
    deck, items, _ = published_deck(n, **kw)
    sub = subscriptions.subscribe(user, deck.id).subscription
    return deck, items, sub


def study(user=ME, *, days_ago=2, stability=20.0, **flt):
    """Make her cards look reviewed (state 2, 20 days of stability, due in 10 days) so a reset has something to soften."""
    now = timezone.now()
    last = now - timedelta(days=days_ago)
    RecallCard.objects.filter(user_id=user, **flt).update(
        state=2, stability=stability, difficulty=5.0, reps=3, last_review_at=last,
        due_scheduled_at=now + timedelta(days=10), due_at=now + timedelta(days=10),
    )  # fmt: skip


def cards_of(item, user=ME):
    return list(RecallCard.objects.filter(user_id=user, item=item).order_by("ordinal"))


def card_of(item, user=ME) -> RecallCard:
    return RecallCard.objects.get(user_id=user, item=item, ordinal=0)


def version_of(sub: RecallSubscription) -> RecallDeckVersion:
    sub.refresh_from_db()
    return sub.synced_version


def new_platform_item(text="Extra", **kw):
    return platform_item(text, **kw)


def unique(text: str) -> str:
    return f"{text} {uuid.uuid4().hex[:6]}?"


def lv(item):
    """The item's live version id, read fresh (the object a test holds is from before the publish)."""
    from modules.recall.models import RecallItem

    return RecallItem.objects.values_list("live_version_id", flat=True).get(pk=item.pk)


def really_review(card, *, days_ago=(12, 5), ratings=(3, 3)):
    """Review a card through the real service (so the log holds the facts and a replay can rebuild the row)."""
    from modules.recall.services.reviews import ReviewIn, submit_review

    now = timezone.now()
    for ago, rating in zip(days_ago, ratings, strict=True):
        submit_review(
            card.user_id,
            ReviewIn(id=uuid.uuid4(), card_id=card.id, rating=rating, reviewed_at=now - timedelta(days=ago)),
        )
    card.refresh_from_db()
    return card
