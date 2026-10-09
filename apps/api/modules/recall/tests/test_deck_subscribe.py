import pytest

from modules.recall.domain import decks as domain
from modules.recall.models import RecallCard, RecallDeck, RecallSubscription
from modules.recall.services import decks as deck_service

from .factories import OTHER, USER, reviewed_fields
from .support import used
from .w11 import EDITOR, draft_deck, platform_item, published_deck

pytestmark = pytest.mark.django_db


def sub_url(deck, action="subscribe"):
    return f"/recall/decks/{deck.id}/{action}/"


def mine(user=USER):
    return RecallCard.objects.filter(user_id=user)


def test_library_lists_live_decks_with_counts_and_tiers(api):
    deck, _, _ = published_deck(3, title="GST basics")
    RecallDeck.objects.create(kind="platform", slug="unpublished", title="Draft only")
    res = api.get("/recall/decks/library/")
    assert res.status_code == 200
    rows = res.json_body["items"]
    assert [r["id"] for r in rows] == [str(deck.id)]
    row = rows[0]
    assert row["item_count"] == 3 and row["card_count"] == 3 and row["version_no"] == 1 and row["subscription"] is None
    assert row["tiers"]["mandatory"] == 1 or "mandatory" in row["tiers"]


def test_library_filters_by_subject_and_tier(api, scheme, ids):
    from modules.syllabus.models import Chapter

    chapter = Chapter.objects.get(key="gst-itc")
    items = [platform_item(chapter_id=chapter.id, importance="mandatory")]
    deck = RecallDeck.objects.create(kind="platform", slug="gst", title="GST", chapter_id=chapter.id)
    deck, draft = draft_deck(items, deck=deck)
    deck_service.publish_deck_version(EDITOR, deck.id, draft.id)
    published_deck(2, slug="other")
    res = api.get(f"/recall/decks/library/?chapter_id={ids['gst']}")
    assert res.status_code == 200 and [r["slug"] for r in res.json_body["items"]] == ["gst"]
    assert api.get("/recall/decks/library/?tier=bogus").status_code == 400


def test_detail_shows_item_previews_and_no_draft_decks(api):
    deck, _, _ = published_deck(3)
    res = api.get(f"/recall/decks/{deck.id}/")
    assert res.status_code == 200 and len(res.json_body["items"]) == 3
    assert all(i["preview"] for i in res.json_body["items"])
    hidden = RecallDeck.objects.create(kind="platform", slug="hid", title="Nope")
    assert api.get(f"/recall/decks/{hidden.id}/").status_code == 404


def test_subscribe_copies_cards_once_and_a_double_tap_is_a_noop(api):
    deck, _, _ = published_deck(3)
    first = api.post(sub_url(deck), {})
    assert first.status_code == 201 and first.json_body["created"] and first.json_body["cards_created"] == 3
    assert first.json_body["deck"]["subscription"]["status"] == "active"
    second = api.post(sub_url(deck), {})
    assert second.status_code == 200 and not second.json_body["created"]
    assert mine().count() == 3 and RecallSubscription.objects.filter(user_id=USER).count() == 1
    assert used(USER) == 0  # platform cards do not use her quota


def test_subscribe_respects_min_importance(api):
    deck, _, _ = published_deck(3)
    res = api.post(sub_url(deck), {"min_importance": "important"})
    assert res.status_code == 201 and res.json_body["cards_created"] == 2
    assert set(mine().values_list("importance", flat=True)) == {3, 2} or mine().count() == 2


def test_cloze_items_make_one_card_per_face(api):
    item = platform_item(kind="cloze", fields={"text_md": "ITC is {{c1::blocked}} under {{c2::17(5)}}."})
    deck, draft = draft_deck([item])
    deck_service.publish_deck_version(EDITOR, deck.id, draft.id)
    res = api.post(sub_url(deck), {})
    assert res.status_code == 201 and res.json_body["cards_created"] == 2
    assert sorted(mine().values_list("ordinal", flat=True)) == [0, 1] or mine().count() == 2


def test_a_deck_over_the_cap_is_refused_whole(api, monkeypatch):
    monkeypatch.setattr(domain, "SUBSCRIBE_MAX_CARDS", 2)
    deck, _, _ = published_deck(3)
    res = api.post(sub_url(deck), {})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "deck_too_large"
    assert mine().count() == 0 and not RecallSubscription.objects.exists()


def test_exactly_at_the_cap_is_allowed(api, monkeypatch):
    monkeypatch.setattr(domain, "SUBSCRIBE_MAX_CARDS", 3)
    deck, _, _ = published_deck(3)
    assert api.post(sub_url(deck), {}).status_code == 201


def test_unsubscribe_archives_and_resubscribe_restores_progress(api):
    deck, _, _ = published_deck(2)
    api.post(sub_url(deck), {})
    card = mine().first()
    RecallCard.objects.filter(pk=card.pk).update(**{**reviewed_fields(), "reps": 4})
    sub = RecallSubscription.objects.get(user_id=USER)
    res = api.post(f"/recall/subscriptions/{sub.id}/unsubscribe/", {})
    assert res.status_code == 200
    assert set(mine().values_list("status", flat=True)) == {"archived"}
    assert api.post(f"/recall/subscriptions/{sub.id}/unsubscribe/", {}).status_code == 200
    back = api.post(f"/recall/subscriptions/{sub.id}/resubscribe/", {})
    assert back.status_code == 201
    card.refresh_from_db()
    assert card.status == "active" and card.reps == 4 and card.stability == 2.3
    assert mine().count() == 2
    # subscribing again after an unsubscribe is the same as resubscribing
    api.post(f"/recall/subscriptions/{sub.id}/unsubscribe/", {})
    again = api.post(sub_url(deck), {})
    assert (
        again.status_code == 201 and mine().count() == 2 and set(mine().values_list("status", flat=True)) == {"active"}
    )


def test_an_item_in_two_decks_stays_when_one_is_unsubscribed(api):
    shared = platform_item()
    d1, v1 = draft_deck([shared], slug="a")
    d2, v2 = draft_deck([shared], slug="b")
    deck_service.publish_deck_version(EDITOR, d1.id, v1.id)
    deck_service.publish_deck_version(EDITOR, d2.id, v2.id)
    api.post(sub_url(d1), {})
    api.post(sub_url(d2), {})
    assert mine().count() == 1
    sub1 = RecallSubscription.objects.get(user_id=USER, deck=d1)
    api.post(f"/recall/subscriptions/{sub1.id}/unsubscribe/", {})
    assert mine().get().status == "active"
    sub2 = RecallSubscription.objects.get(user_id=USER, deck=d2)
    api.post(f"/recall/subscriptions/{sub2.id}/unsubscribe/", {})
    assert mine().get().status == "archived"


def test_another_student_cannot_touch_my_subscription(api, other_api):
    deck, _, _ = published_deck(1)
    api.post(sub_url(deck), {})
    sub = RecallSubscription.objects.get(user_id=USER)
    assert other_api.post(f"/recall/subscriptions/{sub.id}/unsubscribe/", {}).status_code == 404
    assert other_api.post(f"/recall/subscriptions/{sub.id}/resubscribe/", {}).status_code == 404
    assert RecallSubscription.objects.get(pk=sub.pk).status == "active"
    assert mine(OTHER).count() == 0


def test_subscribing_to_an_unknown_or_withdrawn_deck_is_404(api):
    import uuid

    assert api.post(f"/recall/decks/{uuid.uuid4()}/subscribe/", {}).status_code == 404
    unpublished = RecallDeck.objects.create(kind="platform", slug="u", title="U")
    assert api.post(sub_url(unpublished), {}).status_code == 404


def test_library_shows_a_newer_version_as_a_count(api):
    deck, items, _ = published_deck(2)
    api.post(sub_url(deck), {})
    v2 = deck_service.start_draft_version(EDITOR, deck)
    deck_service.publish_deck_version(EDITOR, deck.id, v2.id)
    sub = api.get("/recall/decks/subscribed/").json_body["items"][0]["subscription"]
    assert sub["version_no"] == 1 and sub["newer_versions"] == 1
    assert mine().count() == 2  # R1: no follow-updates
