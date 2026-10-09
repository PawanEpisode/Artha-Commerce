"""Builders for the platform deck tests: items and decks go through the real editor services."""

from __future__ import annotations

import uuid

from modules.recall.models import RecallDeck
from modules.recall.services import decks as deck_service

EDITOR = uuid.UUID("5e1d1a2b-0c3d-4e5f-8a6b-7c8d9e0f1a2b")


def platform_item(
    text="Question", *, importance="bullet", rights="original", kind="pointer", fields=None, ref=None, chapter_id=None
):
    return deck_service.create_platform_item(
        EDITOR,
        kind=kind,
        fields=fields or {"prompt_md": f"{text} {uuid.uuid4().hex[:6]}?", "answer_md": "Answer"},
        importance=importance,
        rights_status=rights,
        external_ref=ref or f"t-{uuid.uuid4().hex[:8]}",
        chapter_id=chapter_id,
    )


def draft_deck(items, *, slug=None, title="Deck", deck=None):
    """A platform deck and a draft version holding these items (the newest version of each)."""
    deck = deck or RecallDeck.objects.create(kind="platform", slug=slug or f"d-{uuid.uuid4().hex[:8]}", title=title)
    draft = deck_service.start_draft_version(EDITOR, deck, from_live=False)
    deck_service.set_draft_rows(draft, [(i, None) for i in items])
    return deck, draft


def published_deck(n=3, *, importances=None, slug=None, title="Deck", **item_extra):
    importances = importances or ["mandatory", "important", "bullet"]
    items = [platform_item(f"Q{i}", importance=importances[i % len(importances)], **item_extra) for i in range(n)]
    deck, draft = draft_deck(items, slug=slug, title=title)
    version = deck_service.publish_deck_version(EDITOR, deck.id, draft.id, changelog_md="First version.")
    deck.refresh_from_db()
    return deck, items, version
