"""R2-W2: a reset card shows up consistently in Today, the queue, the pack, the list and the schedulers (FR-F15-47)."""

from __future__ import annotations

import pytest

from modules.recall.models import RecallCard
from modules.recall.services import sync as sync_service

from .w22 import ME, card_of, deck_with_student, edit, pointer, publish_next, really_review, unique

pytestmark = pytest.mark.django_db


@pytest.fixture
def updated(api):
    deck, items, sub = deck_with_student(3)
    for it in items[:2]:
        really_review(card_of(it))
    edit(items[0], pointer(unique("Changed")), "substantive")
    publish_next(deck)
    sync_service.apply_update(ME, sub.id)
    return deck, items, sub


def test_today_counts_the_cards_to_re_check(api, updated):
    body = api.get("/recall/today/").json_body
    assert body["recheck"]["count"] == 1 and body["needs_chapter"]["count"] == 0


def test_the_queue_pack_and_card_rows_carry_the_note_and_the_badge(api, updated):
    deck, items, _ = updated
    card = card_of(items[0])
    row = api.get(f"/recall/cards/{card.id}/").json_body
    assert row["needs_recheck"] is True and row["recheck_reason"] == "content_changed" and row["updated"] is True
    q = api.get("/recall/queue/?source=today&limit=50").json_body["cards"]
    entry = next(c for c in q if c["id"] == str(card.id))
    assert "updated" in entry["badges"] and entry["updated"] is True and entry["recheck_reason"] == "content_changed"
    pack = api.get("/recall/pack/").json_body
    packed = [c for c in pack.get("cards", []) if c["id"] == str(card.id)]
    assert packed and packed[0]["needs_recheck"] is True and packed[0]["recheck_reason"] == "content_changed"


def test_still_correct_clears_the_note_without_touching_memory(api, updated):
    _, items, _ = updated
    card = card_of(items[0])
    before = (card.stability, card.due_at, card.state)
    res = api.post(f"/recall/cards/{card.id}/recheck-ok/", {"base_rev": card.rev})
    assert res.status_code == 200, res.json_body
    card.refresh_from_db()
    assert not card.needs_recheck and (card.stability, card.due_at, card.state) == before
    assert api.get("/recall/today/").json_body["recheck"]["count"] == 0


def test_rebalance_catch_up_and_bulk_work_with_reset_cards(api, updated):
    assert api.get("/recall/queue/?source=catchup").status_code == 200
    assert api.post("/recall/catchup/rebalance/", {"days": 7}).status_code == 200
    card = card_of(updated[1][0])
    assert card.needs_recheck  # a rebalance never clears the note
    ids = [str(c.id) for c in RecallCard.objects.filter(user_id=ME)]
    res = api.post("/recall/cards/bulk/", {"ids": ids, "action": "suspend"})
    assert res.status_code == 200, res.json_body
