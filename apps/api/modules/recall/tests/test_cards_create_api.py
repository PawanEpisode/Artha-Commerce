import uuid

import pytest

from modules.recall import registry
from modules.recall.models import RecallCard, RecallItem, RecallItemVersion, RecallQuotaPlan

from .factories import USER, make_deck
from .support import POINTER, distinct, made, new, row, used

pytestmark = pytest.mark.django_db


def test_create_a_pointer_card_stores_a_new_card_with_no_memory_state(api, ids, scheme):
    res = new(api, chapter_id=ids["gst"], importance="mandatory", tags=["itc", "gst"], reference_keys=["cgst:17(5)"])
    assert res.status_code == 201
    body = res.json_body
    assert body["kind"] == "pointer" and body["existing"] is False and len(body["cards"]) == 1
    card = body["cards"][0]
    assert card["front_md"] == POINTER["prompt_md"] and card["back_md"] == POINTER["answer_md"]
    assert card["state"] == 0 and card["importance"] == "mandatory" and card["rev"] == 1
    assert card["chapter"]["key"] == "gst-itc" and card["tags"] == ["itc", "gst"] and card["badges"] == []
    assert card["source"] is None and card["fields"]["v"] == 1
    db = row(card["id"])
    assert (db.state, db.stability, db.difficulty, db.due_at, db.reps) == (0, None, None, None, 0)
    assert db.importance == 2 and db.subject_key == "taxation" and db.scheduler_version == "fsrs-6.0"
    assert db.params is not None and db.params.scope == "default"
    item = db.item
    assert (item.ownership, item.owner_user_id, item.status, item.rights_status) == ("user", USER, "active", "original")
    assert item.chapter_key == "gst-itc" and item.subject_key == "taxation" and item.course_id and item.level_id
    assert item.shareable is True and item.origin == "manual" and item.reference_keys == ["cgst:17(5)"]
    assert item.search_text.startswith("When is ITC blocked?") and len(item.fingerprint) == 64
    version = db.item_version
    assert (version.version_no, version.state, version.change_kind, version.authored_by) == (1, "live", "create", USER)
    assert item.live_version_id == item.current_version_id == version.id
    assert used(USER) == 1


@pytest.mark.parametrize("spec", registry.all_kinds(), ids=lambda s: s.name)
def test_every_kind_can_be_created_from_its_example(api, spec):
    res = new(api, dict(spec.example_fields), kind=spec.name)
    assert res.status_code == 201, res.json_body
    assert (
        res.json_body["kind"] == spec.name
        and res.json_body["cards"][0]["ordinal"] == spec.ordinals(spec.example_fields)[0]
    )


def test_a_cloze_makes_one_card_per_deletion_and_reserves_that_many_slots(api):
    text = "The {{c1::Companies Act, 2013}} replaced the {{c2::1956}} Act in {{c3::2013}}."
    res = new(api, {"text_md": text}, kind="cloze")
    assert res.status_code == 201
    cards = res.json_body["cards"]
    assert [c["ordinal"] for c in cards] == [1, 2, 3]
    assert "[...]" in cards[0]["front_md"] and "**Companies Act, 2013**" in cards[0]["back_md"]
    assert used(USER) == 3
    assert RecallItem.objects.get(pk=res.json_body["item_id"]).live_version.cloze_count == 3


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"prompt_md": "![x](https://a/b.png)", "answer_md": "A"}, "too_many_images"),
        ({"prompt_md": "# Heading", "answer_md": "A"}, None),
        ({"prompt_md": "Q", "answer_md": "x" * 4001}, "too_long"),
        ({"prompt_md": "Q"}, "required"),
        ({"prompt_md": "Q", "answer_md": "A", "extra": "x"}, "unknown_field"),
        ({"prompt_md": "Q", "answer_md": 5}, "not_text"),
    ],
)
def test_invalid_fields_are_422_with_per_field_issues_and_nothing_is_written(api, fields, code):
    res = new(api, fields)
    assert res.status_code == 422 and res.json_body["error"]["code"] == "invalid_fields"
    errors = res.json_body["error"]["details"]["errors"]
    assert errors and all({"field", "code", "message"} <= set(e) for e in errors)
    if code:
        assert code in {e["code"] for e in errors}
    assert RecallItem.objects.count() == 0 and used(USER) == 0


def test_a_horizontal_rule_and_a_heading_are_refused_by_the_card_profile(api):
    for text in ("above\n\n---\n\nbelow", "## Title\ntext"):
        res = new(api, {"prompt_md": "Q", "answer_md": text})
        assert res.status_code == 422, text
        assert res.json_body["error"]["details"]["errors"][0]["field"] == "answer_md"


def test_unknown_kind_and_unknown_chapter_are_422(api):
    assert new(api, kind="riddle").json_body["error"]["code"] == "unknown_kind"
    res = new(api, chapter_id=str(uuid.uuid4()))
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_chapter"


def test_tag_and_reference_key_limits(api):
    assert (
        new(api, tags=[f"t{i}" for i in range(13)]).json_body["error"]["details"]["errors"][0]["code"]
        == "too_many_tags"
    )
    assert new(api, tags=["x" * 41]).json_body["error"]["details"]["errors"][0]["code"] == "tag_too_long"
    assert new(api, tags=[""]).status_code == 422
    ok = new(api, tags=[f"tag{i}" for i in range(12)], reference_keys=["a:1"] * 3)
    assert ok.status_code == 201 and len(ok.json_body["cards"][0]["tags"]) == 12
    assert ok.json_body["cards"][0]["reference_keys"] == ["a:1"]  # duplicates collapse
    assert (
        new(
            api, fields={"prompt_md": "Another one?", "answer_md": "B"}, reference_keys=["k"] * 0 + ["z" * 81]
        ).status_code
        == 422
    )
    assert new(api, importance="urgent").json_body["error"]["details"]["errors"][0]["code"] == "bad_importance"


def test_missing_client_id_or_fields_is_400(api):
    assert api.post("/recall/cards/", {"kind": "pointer", "fields": POINTER}).status_code == 400
    assert api.post("/recall/cards/", {"client_id": str(uuid.uuid4()), "kind": "pointer"}).status_code == 400


def test_a_replay_with_the_same_client_id_returns_the_first_cards(api):
    client_id = str(uuid.uuid4())
    first = api.post("/recall/cards/", {"client_id": client_id, "kind": "pointer", "fields": POINTER})
    again = api.post("/recall/cards/", {"client_id": client_id, "kind": "pointer", "fields": POINTER})
    assert first.status_code == 201 and again.status_code == 200
    assert (
        again.json_body["existing"] is True and again.json_body["cards"][0]["id"] == first.json_body["cards"][0]["id"]
    )
    assert RecallCard.objects.count() == 1 and used(USER) == 1


def test_a_client_id_belongs_to_one_student(api, other_api):
    client_id = str(uuid.uuid4())
    body = {"client_id": client_id, "kind": "pointer", "fields": POINTER}
    assert api.post("/recall/cards/", body).status_code == 201
    assert other_api.post("/recall/cards/", body).status_code == 201


def test_a_duplicate_is_409_with_the_existing_card_and_force_keeps_both(api):
    first = made(api)
    res = new(api, {"prompt_md": "  when is ITC   blocked? ", "answer_md": "Under SECTION 17(5)."})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "duplicate_card"
    assert res.json_body["error"]["details"]["card_id"] == first["id"]
    assert RecallCard.objects.count() == 1 and used(USER) == 1
    forced = new(api, dict(POINTER), force=True)
    assert forced.status_code == 201 and RecallCard.objects.count() == 2


def test_a_duplicate_of_a_deleted_card_is_not_a_duplicate(api):
    first = made(api)
    assert api.delete(f"/recall/cards/{first['id']}/").status_code == 200
    assert new(api).status_code == 201


def test_another_students_identical_card_is_not_a_duplicate(api, other_api):
    made(other_api)
    assert new(api).status_code == 201


# --- quota ------------------------------------------------------------------------------------------------------------
def set_limit(**kwargs):
    RecallQuotaPlan.objects.filter(pk="free").update(**kwargs)


def test_the_last_slot_is_usable_and_the_next_card_is_429_with_details(api):
    set_limit(max_cards=2)
    made(api, distinct(1)[0])
    made(api, distinct(2)[1])
    res = new(api, {"prompt_md": "One more?", "answer_md": "x"})
    assert res.status_code == 429 and res.json_body["error"]["code"] == "quota_exceeded"
    assert res.json_body["error"]["details"] == {"kind": "cards", "used": 2, "limit": 2, "plan": "free"}
    assert RecallCard.objects.count() == 2 and used(USER) == 2


def test_a_cloze_that_does_not_fit_changes_nothing(api):
    set_limit(max_cards=2)
    made(api, distinct(1)[0])
    res = new(api, {"text_md": "{{c1::a}} {{c2::b}} {{c3::c}}"}, kind="cloze")
    assert res.status_code == 429 and RecallItem.objects.count() == 1 and used(USER) == 1
    assert new(api, {"text_md": "{{c1::a}} only"}, kind="cloze").status_code == 201  # one slot is still free


def test_the_per_deck_limit_refuses_and_changes_nothing(api):
    set_limit(max_cards_per_deck=1)
    deck = make_deck(USER)
    assert new(api, deck_ids=[str(deck.id)]).status_code == 201
    res = new(api, {"prompt_md": "Q2?", "answer_md": "A2"}, deck_ids=[str(deck.id)])
    assert res.status_code == 429 and res.json_body["error"]["details"]["kind"] == "cards_per_deck"
    deck.refresh_from_db()
    assert deck.card_count == 1 and used(USER) == 1 and RecallItem.objects.count() == 1


def test_another_students_or_unknown_deck_is_404_and_nothing_is_reserved(api, other_api):
    theirs = make_deck(uuid.UUID("9a1e7c52-1a5b-4d6e-8c3f-2b7d4e5f6a70"))
    assert new(api, deck_ids=[str(theirs.id)]).status_code == 404
    assert new(api, deck_ids=[str(uuid.uuid4())]).status_code == 404
    assert used(USER) == 0 and RecallItem.objects.count() == 0


def test_deck_membership_is_recorded_and_counted(api):
    deck = make_deck(USER)
    res = new(api, {"text_md": "{{c1::a}} and {{c2::b}}"}, kind="cloze", deck_ids=[str(deck.id)])
    assert res.status_code == 201 and res.json_body["cards"][0]["deck_ids"] == [str(deck.id)]
    deck.refresh_from_db()
    assert deck.card_count == 2 and deck.members.count() == 1


def test_a_new_version_row_exists_only_once(api):
    card = made(api)
    assert RecallItemVersion.objects.filter(item_id=card["item_id"]).count() == 1
