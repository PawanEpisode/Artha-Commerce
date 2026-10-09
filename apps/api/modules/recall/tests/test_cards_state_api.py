import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.recall.models import RecallCard, RecallDeck, RecallQuotaPlan, RecallScheduleEvent
from modules.recall.services import cards as services

from .factories import USER, make_card, make_deck, reviewed_fields
from .support import distinct, made, new, row, used

pytestmark = pytest.mark.django_db


def act(api, card, action, body=None):
    return api.post(f"/recall/cards/{card['id']}/{action}/", body or {})


def test_suspend_and_unsuspend_return_the_card_and_leave_memory_alone(api):
    card = made(api)
    RecallCard.objects.filter(pk=card["id"]).update(**reviewed_fields())
    before = row(card["id"])
    res = act(api, card, "suspend")
    assert res.status_code == 200 and res.json_body["status"] == "suspended" and "suspended" in res.json_body["badges"]
    assert row(card["id"]).suspend_reason == "manual"
    assert act(api, card, "unsuspend").json_body["status"] == "active"
    after = row(card["id"])
    assert (after.stability, after.due_at, after.state) == (before.stability, before.due_at, before.state)
    assert list(RecallScheduleEvent.objects.order_by("at").values_list("kind", flat=True)) == ["suspend", "unsuspend"]


def test_bury_lasts_until_the_end_of_the_study_day_or_the_given_time(api):
    card = made(api)
    res = act(api, card, "bury")
    until = row(card["id"]).buried_until
    assert res.status_code == 200 and "buried" in res.json_body["badges"]
    assert timezone.now() < until <= timezone.now() + timedelta(hours=24)
    later = (timezone.now() + timedelta(days=2)).isoformat()
    assert act(api, card, "bury", {"until": later}).status_code == 200
    assert row(card["id"]).buried_until > until
    assert act(api, card, "bury", {"until": (timezone.now() - timedelta(hours=1)).isoformat()}).status_code == 422
    assert act(api, card, "bury", {"until": (timezone.now() + timedelta(days=30)).isoformat()}).status_code == 422


def test_reset_returns_the_card_to_new_and_writes_a_forget_event(api):
    card = made(api)
    RecallCard.objects.filter(pk=card["id"]).update(**reviewed_fields(), lapses=2, leech=True)
    res = act(api, card, "reset")
    assert res.status_code == 200 and res.json_body["state"] == 0
    db = row(card["id"])
    assert (db.state, db.stability, db.difficulty, db.due_at, db.reps, db.lapses, db.leech) == (
        0,
        None,
        None,
        None,
        0,
        0,
        False,
    )
    event = RecallScheduleEvent.objects.get(card_id=card["id"])
    assert event.kind == "forget" and event.stability_before == 2.3 and event.reason_code == "student"


def test_recheck_ok_clears_the_flag(api):
    card = made(api)
    RecallCard.objects.filter(pk=card["id"]).update(needs_recheck=True, recheck_reason="content_changed")
    assert "recheck" in api.get(f"/recall/cards/{card['id']}/").json_body["badges"]
    res = act(api, card, "recheck-ok")
    assert res.status_code == 200 and res.json_body["badges"] == []
    assert row(card["id"]).recheck_reason is None


def test_state_actions_on_others_or_deleted_cards(api, other_api):
    card = made(api)
    for action in ("suspend", "unsuspend", "bury", "reset", "recheck-ok"):
        assert act(other_api, card, action).status_code == 404
    api.delete(f"/recall/cards/{card['id']}/")
    assert act(api, card, "suspend").status_code == 410


# --- delete and undo ---------------------------------------------------------------------------------------------------
def test_delete_is_soft_releases_quota_and_hands_out_an_undo_token(api):
    card = made(api)
    assert used(USER) == 1
    res = api.delete(f"/recall/cards/{card['id']}/")
    assert res.status_code == 200 and res.json_body["undo_token"] and res.json_body["undo_seconds"] == 10
    db = row(card["id"])
    assert db.status == "deleted" and db.deleted_at and db.item.status == "deleted" and db.item.deleted_at
    assert used(USER) == 0
    assert api.get("/recall/cards/").json_body["items"] == []
    assert api.delete(f"/recall/cards/{card['id']}/").status_code == 410


def test_undo_restores_the_card_and_reserves_the_quota_again(api):
    card = made(api)
    token = api.delete(f"/recall/cards/{card['id']}/").json_body["undo_token"]
    res = api.post("/recall/cards/undo-delete/", {"undo_token": token})
    assert res.status_code == 200 and res.json_body["status"] == "active" and res.json_body["rev"] == 3
    assert used(USER) == 1 and row(card["id"]).item.status == "active"
    assert api.post("/recall/cards/undo-delete/", {"undo_token": token}).status_code == 200  # idempotent


def test_undo_keeps_a_suspended_card_suspended(api):
    card = made(api)
    act(api, card, "suspend")
    token = api.delete(f"/recall/cards/{card['id']}/").json_body["undo_token"]
    assert api.post("/recall/cards/undo-delete/", {"undo_token": token}).json_body["status"] == "suspended"


def test_undo_after_ten_seconds_is_410(api, monkeypatch):
    card = made(api)
    token = api.delete(f"/recall/cards/{card['id']}/").json_body["undo_token"]
    monkeypatch.setattr(services, "UNDO_SECONDS", -1)  # every token is now older than its max age
    res = api.post("/recall/cards/undo-delete/", {"undo_token": token})
    assert res.status_code == 410 and res.json_body["error"]["code"] == "undo_expired"
    assert row(card["id"]).status == "deleted" and used(USER) == 0


def test_a_token_of_another_student_or_a_forged_one_is_404(api, other_api):
    card = made(api)
    token = api.delete(f"/recall/cards/{card['id']}/").json_body["undo_token"]
    assert other_api.post("/recall/cards/undo-delete/", {"undo_token": token}).status_code == 404
    assert api.post("/recall/cards/undo-delete/", {"undo_token": token + "x"}).status_code == 404
    assert api.post("/recall/cards/undo-delete/", {}).status_code == 400


def test_undo_when_the_plan_filled_up_meanwhile_is_429_and_changes_nothing(api):
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=1)
    card = made(api)
    token = api.delete(f"/recall/cards/{card['id']}/").json_body["undo_token"]
    made(api, distinct(1)[0])
    res = api.post("/recall/cards/undo-delete/", {"undo_token": token})
    assert res.status_code == 429 and row(card["id"]).status == "deleted" and used(USER) == 1


def test_deleting_a_cloze_removes_every_face_and_undo_brings_them_back(api):
    res = new(api, {"text_md": "{{c1::a}} {{c2::b}}"}, kind="cloze")
    first = res.json_body["cards"][0]
    token = api.delete(f"/recall/cards/{first['id']}/").json_body["undo_token"]
    assert used(USER) == 0 and RecallCard.objects.filter(status="deleted").count() == 2
    api.post("/recall/cards/undo-delete/", {"undo_token": token})
    assert used(USER) == 2 and RecallCard.objects.filter(status="active").count() == 2


def test_delete_and_undo_keep_the_deck_counter_in_step(api):
    deck = make_deck(USER)
    card = made(api, deck_ids=[str(deck.id)])
    assert RecallDeck.objects.get(pk=deck.id).card_count == 1
    token = api.delete(f"/recall/cards/{card['id']}/").json_body["undo_token"]
    assert RecallDeck.objects.get(pk=deck.id).card_count == 0
    api.post("/recall/cards/undo-delete/", {"undo_token": token})
    assert RecallDeck.objects.get(pk=deck.id).card_count == 1


# --- bulk --------------------------------------------------------------------------------------------------------------
def bulk(api, ids, action, **extra):
    return api.post("/recall/cards/bulk/", {"ids": ids, "action": action, **extra})


def three(api):
    return [made(api, f) for f in distinct(3)]


def test_bulk_actions_apply_to_every_card(api, ids):
    cards = three(api)
    pick = [c["id"] for c in cards]
    assert bulk(api, pick, "set_importance", importance="mandatory").json_body == {"count": 3}
    assert {row(i).importance for i in pick} == {2}
    assert bulk(api, pick, "move_chapter", chapter_id=ids["gst"]).status_code == 200
    assert {row(i).item.chapter_key for i in pick} == {"gst-itc"} and {row(i).subject_key for i in pick} == {"taxation"}
    assert bulk(api, pick, "add_tag", tag="revise").status_code == 200
    assert all(row(i).item.tags == ["revise"] for i in pick)
    assert bulk(api, pick[:2], "suspend").status_code == 200
    assert [row(i).status for i in pick] == ["suspended", "suspended", "active"]
    deck = make_deck(USER)
    assert bulk(api, pick, "add_to_deck", deck_id=str(deck.id)).status_code == 200
    assert RecallDeck.objects.get(pk=deck.id).card_count == 3
    assert bulk(api, pick, "add_to_deck", deck_id=str(deck.id)).status_code == 200  # already members: no double count
    assert RecallDeck.objects.get(pk=deck.id).card_count == 3
    assert bulk(api, pick, "delete").status_code == 200 and used(USER) == 0


def test_bulk_is_all_or_none_when_one_id_is_not_the_students(api, other_api):
    mine = made(api)
    theirs = made(other_api, distinct(1)[0])
    res = bulk(api, [mine["id"], theirs["id"]], "set_importance", importance="mandatory")
    assert res.status_code == 404 and row(mine["id"]).importance == 0
    assert row(theirs["id"]).importance == 0


def test_bulk_is_all_or_none_when_the_quota_fails_midway(api):
    cards = three(api)
    deck = make_deck(USER)
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards_per_deck=2)
    res = bulk(api, [c["id"] for c in cards], "add_to_deck", deck_id=str(deck.id))
    assert res.status_code == 429 and RecallDeck.objects.get(pk=deck.id).card_count == 0
    assert not deck.members.exists()


def test_bulk_takes_at_most_200_ids_and_a_deleted_card_aborts_it(api):
    mine = made(api)
    too_many = [str(uuid.uuid4()) for _ in range(201)]
    res = bulk(api, too_many, "suspend")
    assert res.status_code == 422 and res.json_body["error"]["code"] == "bulk_too_large"
    assert bulk(api, [], "suspend").status_code == 400
    assert bulk(api, [mine["id"]], "explode").status_code == 400
    assert bulk(api, [mine["id"]], "set_importance").status_code == 400  # the argument is missing
    api.delete(f"/recall/cards/{mine['id']}/")
    assert bulk(api, [mine["id"]], "suspend").status_code == 404


def test_a_bulk_of_exactly_200_cards_is_accepted(api):
    ids = [str(make_card().id) for _ in range(services.BULK_MAX)]
    assert bulk(api, ids, "suspend").json_body == {"count": 200}
    assert RecallCard.objects.filter(status="suspended").count() == 200
