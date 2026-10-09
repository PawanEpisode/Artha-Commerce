import pytest

from modules.recall.models import RecallCard, RecallItemVersion, RecallQuotaPlan

from .factories import reviewed_fields
from .support import distinct, made, new, row, used

pytestmark = pytest.mark.django_db


def patch(api, card, **body):
    return api.patch(f"/recall/cards/{card['id']}/", {"base_rev": card["rev"], **body})


def test_a_text_edit_makes_a_new_live_version_and_supersedes_the_old_one(api):
    card = made(api)
    res = patch(api, card, fields={"answer_md": "Motor vehicles, food and club fees."})
    assert res.status_code == 200
    body = res.json_body
    assert body["back_md"] == "Motor vehicles, food and club fees." and body["front_md"] == card["front_md"]
    assert body["rev"] == 2 and body["item_version_id"] != card["item_version_id"]
    versions = list(RecallItemVersion.objects.filter(item_id=card["item_id"]).order_by("version_no"))
    assert [(v.version_no, v.state) for v in versions] == [(1, "superseded"), (2, "live")]
    assert versions[1].change_kind == "clarify" and versions[0].superseded_at is not None
    item = row(card["id"]).item
    assert item.live_version_id == versions[1].id == item.current_version_id
    assert "Motor vehicles" in item.search_text
    assert api.get(f"/recall/cards/{card['id']}/").json_body["fields"]["answer_md"].startswith("Motor")


def test_editing_never_changes_the_memory_state(api):
    card = made(api)
    RecallCard.objects.filter(pk=card["id"]).update(**reviewed_fields(5))
    before = row(card["id"])
    assert patch(api, card, fields={"prompt_md": "Reworded question?"}).status_code == 200
    after = row(card["id"])
    for name in ("state", "stability", "difficulty", "due_at", "reps", "last_review_at"):
        assert getattr(after, name) == getattr(before, name), name


def test_a_stale_base_rev_is_409_with_the_server_fields_and_nothing_changes(api):
    card = made(api)
    assert patch(api, card, tags=["a"]).status_code == 200
    stale = patch(api, card, fields={"answer_md": "Mine"})
    assert stale.status_code == 409 and stale.json_body["error"]["code"] == "edit_conflict"
    details = stale.json_body["error"]["details"]
    assert details["rev"] == 2 and details["server_fields"]["answer_md"] == card["fields"]["answer_md"]
    assert RecallItemVersion.objects.filter(item_id=card["item_id"]).count() == 1


def test_a_metadata_edit_bumps_rev_without_a_new_version(api, ids):
    card = made(api)
    res = patch(api, card, importance="important", tags=["itc"], chapter_id=ids["gst"])
    body = res.json_body
    assert res.status_code == 200 and body["rev"] == 2 and body["item_version_id"] == card["item_version_id"]
    assert body["importance"] == "important" and body["tags"] == ["itc"] and body["chapter"]["key"] == "gst-itc"
    db = row(card["id"])
    assert (db.importance, db.chapter_id, db.subject_key) == (1, db.item.chapter_id, "taxation")
    assert db.item.chapter_key == "gst-itc"
    cleared = patch(api, body, chapter_id=None)
    assert cleared.json_body["chapter"] is None and row(card["id"]).item.chapter_key is None


def test_an_edit_that_changes_nothing_does_not_bump_rev(api):
    card = made(api)
    res = patch(api, card, fields={"answer_md": card["fields"]["answer_md"]}, tags=[])
    assert res.status_code == 200 and res.json_body["rev"] == 1


def test_moving_to_an_unknown_chapter_is_422(api):
    card = made(api)
    res = patch(api, card, chapter_id="3f2b8c7e-0000-4f0e-9a45-0f9e5b3e1c11")
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_chapter"


def test_invalid_edits_are_422_and_the_kind_cannot_change(api):
    card = made(api)
    assert patch(api, card, fields={"answer_md": "## no"}).status_code == 422
    res = patch(api, card, fields={"term": "x"})  # a field of another kind
    assert res.status_code == 422 and res.json_body["error"]["details"]["errors"][0]["code"] == "unknown_field"
    assert api.patch(f"/recall/cards/{card['id']}/", {"fields": {}}).status_code == 400  # base_rev is required


def test_other_students_and_deleted_cards(api, other_api):
    card = made(api)
    assert patch(other_api, card, tags=["x"]).status_code == 404
    assert other_api.get(f"/recall/cards/{card['id']}/").status_code == 404
    assert other_api.delete(f"/recall/cards/{card['id']}/").status_code == 404
    assert api.delete(f"/recall/cards/{card['id']}/").status_code == 200
    assert patch(api, card, tags=["x"]).status_code == 410
    assert api.get(f"/recall/cards/{card['id']}/").json_body["error"]["code"] == "card_deleted"


def test_editing_a_cloze_can_add_a_face_and_remove_the_last_one(api):
    res = new(api, {"text_md": "{{c1::a}} then {{c2::b}}"}, kind="cloze")
    first = res.json_body["cards"][0]
    grown = patch(api, first, fields={"text_md": "{{c1::a}} then {{c2::b}} then {{c3::c}}"})
    assert grown.status_code == 200 and used_faces(res.json_body["item_id"]) == [1, 2, 3] and used_total() == 3
    siblings = RecallCard.objects.filter(item_id=res.json_body["item_id"])
    assert len({c.item_version_id for c in siblings}) == 1  # every face points at the new version
    shrunk = patch(api, grown.json_body, fields={"text_md": "{{c1::a}} then {{c2::b}}"})
    assert shrunk.status_code == 200 and used_faces(res.json_body["item_id"]) == [1, 2] and used_total() == 2
    removing_own = patch(
        api, api.get(f"/recall/cards/{siblings.get(ordinal=2).id}/").json_body, fields={"text_md": "{{c1::a}} only"}
    )
    assert removing_own.status_code == 422


def used_faces(item_id):
    return sorted(
        RecallCard.objects.filter(item_id=item_id).exclude(status="deleted").values_list("ordinal", flat=True)
    )


def used_total():

    from .factories import USER

    return used(USER)


def test_adding_a_face_that_does_not_fit_the_quota_changes_nothing(api):
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=2)
    res = new(api, {"text_md": "{{c1::a}} then {{c2::b}}"}, kind="cloze")
    first = res.json_body["cards"][0]
    refused = patch(api, first, fields={"text_md": "{{c1::a}} then {{c2::b}} then {{c3::c}}"})
    assert refused.status_code == 429
    assert RecallItemVersion.objects.filter(item_id=res.json_body["item_id"]).count() == 1
    assert used_faces(res.json_body["item_id"]) == [1, 2] and used_total() == 2


def test_get_never_writes(api):
    card = made(api)
    before = row(card["id"]).updated_at
    for _ in range(2):
        assert api.get(f"/recall/cards/{card['id']}/").status_code == 200
        assert api.get("/recall/cards/").status_code == 200
    assert row(card["id"]).updated_at == before and RecallCard.objects.count() == 1


def test_distinct_helper_makes_distinct_cards(api):
    assert len({made(api, f)["id"] for f in distinct(3)}) == 3
