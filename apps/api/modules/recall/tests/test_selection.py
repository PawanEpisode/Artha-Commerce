import uuid

import pytest

from modules.recall import registry
from modules.recall.services import cards as services

from .support import row

pytestmark = pytest.mark.django_db


def pick(api, text, **extra):
    body = {
        "client_id": str(uuid.uuid4()),
        "origin": "note_highlight",
        "selection_text": text,
        "source": {"module": "notes", "object_id": str(uuid.uuid4()), "locator": {"page": 12, "annotation_id": "abc"}},
        **extra,
    }
    return api.post("/recall/cards/from-selection/", body)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Section 17(5) blocks credit on motor vehicles", "section"),
        ("Break-even = Fixed cost / Contribution", "formula"),
        ("Goodwill means an intangible asset from a combination", "definition"),
        ("Salomon v. Salomon decided by the House of Lords, a High Court style ruling", "case_law"),
        ("Remember the three tests of control", "pointer"),
    ],
)
def test_the_kind_is_suggested_by_rules(api, text, kind):
    res = pick(api, text)
    assert res.status_code == 201, res.json_body
    assert res.json_body["kind"] == kind and res.json_body["card_id"] == res.json_body["cards"][0]["id"]
    assert res.json_body["undo_token"] and res.json_body["undo_seconds"] == 10


def test_a_selection_card_records_its_source_and_is_not_shareable(api):
    res = pick(api, "Goodwill means an intangible asset")
    item = row(res.json_body["card_id"]).item
    assert (item.origin, item.origin_module, item.shareable) == ("selection", "notes", False)
    assert item.origin_locator == {"v": 1, "page": 12, "annotation_id": "abc"}
    source = res.json_body["cards"][0]["source"]
    assert source["module"] == "notes" and source["locator"]["page"] == 12
    assert res.json_body["cards"][0]["fields"]["term"] == "Goodwill"


@pytest.mark.parametrize(
    ("origin", "item_origin"),
    [("solution_text", "solution"), ("question_review", "mistake"), ("chapter_page", "selection")],
)
def test_origins_map_to_item_origins(api, origin, item_origin):
    res = pick(api, "A point worth keeping", origin=origin)
    assert res.status_code == 201 and row(res.json_body["card_id"]).item.origin == item_origin


def test_a_chapter_page_source_of_the_syllabus_is_kept_in_the_locator_only(api):
    res = pick(
        api,
        "A point worth keeping",
        origin="chapter_page",
        source={"module": "syllabus", "object_id": "abc", "locator": {}},
    )
    item = row(res.json_body["card_id"]).item
    assert res.status_code == 201 and item.origin_module is None


def test_the_locator_never_carries_text(api):
    long_text = "x" * 200
    res = pick(
        api,
        "Another point",
        source={
            "module": "notes",
            "object_id": "n1",
            "locator": {"page": 1, "quote": long_text, "range": [1, 2], "bad": {"a": 1}},
        },
    )
    assert row(res.json_body["card_id"]).item.origin_locator == {"v": 1, "page": 1, "range": [1, 2]}


def test_an_explicit_kind_wins_and_a_replay_is_idempotent(api):
    client_id = str(uuid.uuid4())
    first = pick(api, "Rule: three tests apply", kind="pointer", client_id=client_id)
    again = pick(api, "Rule: three tests apply", kind="pointer", client_id=client_id)
    assert first.status_code == 201 and again.status_code == 200 and again.json_body["existing"] is True
    assert again.json_body["card_id"] == first.json_body["card_id"] and again.json_body["undo_token"] is None
    assert first.json_body["cards"][0]["fields"] == {"v": 1, "prompt_md": "Rule?", "answer_md": "three tests apply"}


def test_the_cloze_toggle_wraps_the_tail(api):
    res = pick(api, "Goodwill is an intangible asset arising on acquisition", kind="cloze", cloze=True)
    assert res.status_code == 201 and res.json_body["kind"] == "cloze"
    assert "{{c1::" in res.json_body["cards"][0]["fields"]["text_md"]
    already = pick(api, "A {{c1::given}} deletion", kind="cloze")
    assert already.json_body["cards"][0]["fields"]["text_md"] == "A {{c1::given}} deletion"


def test_a_selection_of_the_same_text_twice_is_a_duplicate_unless_forced(api):
    assert pick(api, "Same words every time").status_code == 201
    dup = pick(api, "Same words every time")
    assert dup.status_code == 409 and dup.json_body["error"]["code"] == "duplicate_card"
    assert pick(api, "Same words every time", force=True).status_code == 201


def test_an_empty_selection_or_unknown_origin_is_rejected(api):
    assert pick(api, "   ").status_code == 422
    assert pick(api, "text", origin="elsewhere").status_code == 400
    assert pick(api, "text", kind="riddle").json_body["error"]["code"] == "unknown_kind"


def test_the_undo_token_of_a_new_selection_card_deletes_it(api):
    res = pick(api, "Remember the three tests of control")
    undone = api.post("/recall/cards/undo-delete/", {"undo_token": res.json_body["undo_token"]})
    assert undone.status_code == 200 and undone.json_body["status"] == "deleted"
    assert row(res.json_body["card_id"]).status == "deleted"


def test_selection_fields_are_pure_and_fit_the_limits():
    big = "word " * 3000
    for spec in registry.all_kinds():
        fields = services.fields_for_selection(spec.name, big)
        assert spec.validate(fields) == [], spec.name
    assert services.fields_for_selection("pointer", "First\n\nSecond") == {"prompt_md": "First", "answer_md": "Second"}
