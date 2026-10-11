"""R2-W4 A: a card from a mistake (`POST /recall/cards/from-question/`, FR-F15-17): the source comes from the question bank, never a model."""

from __future__ import annotations

import logging
import uuid

import pytest

from core import question_port
from core.question_port import QuestionSource
from modules.recall.models import RecallCard, RecallItem, RecallQuotaPlan

from .factories import USER
from .support import used

pytestmark = pytest.mark.django_db
URL = "/recall/cards/from-question/"
QID, VID = uuid.uuid4(), uuid.uuid4()
EXPLANATION = "ITC on motor cars is blocked under section 17(5) unless the car is used to supply cars or for transport."


class Bank:
    """A stand-in for F-06: a dict of question id to source (or None)."""

    def __init__(self):
        self.sources: dict = {}
        self.asked: list = []

    def source_for(self, user_id, question_id, version_id):
        self.asked.append((str(user_id), question_id, version_id))
        return self.sources.get(question_id)


@pytest.fixture
def bank():
    b = Bank()
    question_port.register_question_provider(b)
    yield b
    question_port.register_question_provider(None)


def src(**kw):
    base = {
        "question_id": QID,
        "version_id": VID,
        "explanation_md": EXPLANATION,
        "reference_labels": ("Section 17(5), CGST Act",),
        "reference_keys": ("cgst:17(5)",),
    }
    return QuestionSource(**{**base, **kw})


def send(api, **extra):
    return api.post(URL, {"question_id": str(QID), "version_id": str(VID), **extra})


def test_a_wrong_answer_becomes_a_pointer_card_that_quotes_the_explanation_and_its_source(api, bank, ids):
    bank.sources[QID] = src(chapter_id=uuid.UUID(ids["gst"]))
    res = send(api)
    body = res.json_body
    assert res.status_code == 201, body
    card = body["cards"][0]
    assert card["kind"] == "pointer" and card["front_md"] == "What is the rule in Section 17(5), CGST Act?"
    assert EXPLANATION in card["back_md"] and card["back_md"].endswith("Source: Section 17(5), CGST Act")
    assert card["chapter"]["id"] == ids["gst"] and card["reference_keys"] == ["cgst:17(5)"]
    assert body["undo_token"] and body["card_id"] == card["id"]
    item = RecallItem.objects.get(pk=body["item_id"])
    assert (item.origin, item.origin_module, item.origin_ref, item.origin_kind) == (
        "mistake",
        "questionbank",
        str(QID),
        "question_mistake",
    )
    assert item.shareable is False and item.origin_locator["version_id"] == str(VID)
    assert used(USER) == 1


def test_a_second_tap_returns_the_same_card_and_uses_no_quota(api, bank):
    bank.sources[QID] = src()
    first = send(api).json_body
    again = send(api)
    assert again.status_code == 200 and again.json_body["existing"] is True
    assert again.json_body["card_id"] == first["card_id"] and again.json_body["undo_token"] is None
    assert RecallCard.objects.count() == 1 and used(USER) == 1


def test_a_replay_with_the_same_client_id_is_the_same_card(api, bank):
    bank.sources[QID] = src()
    cid = str(uuid.uuid4())
    a, b = send(api, client_id=cid), send(api, client_id=cid)
    assert (a.status_code, b.status_code) == (201, 200) and a.json_body["card_id"] == b.json_body["card_id"]


def test_a_deleted_card_can_be_made_again(api, bank):
    bank.sources[QID] = src()
    first = send(api).json_body
    assert api.delete(f"/recall/cards/{first['card_id']}/").status_code == 200
    second = send(api)
    assert second.status_code == 201 and second.json_body["card_id"] != first["card_id"]


def test_with_no_question_bank_it_is_503(api):
    res = send(api)
    assert res.status_code == 503 and res.json_body["error"]["code"] == "question_source_unavailable"


def test_a_question_the_bank_does_not_know_is_404(api, bank):
    res = send(api)
    assert res.status_code == 404 and RecallCard.objects.count() == 0


def test_a_question_with_nothing_to_quote_is_422_and_nothing_is_made(api, bank):
    bank.sources[QID] = src(explanation_md="  ", reference_labels=(), reference_keys=())
    res = send(api)
    assert res.status_code == 422 and res.json_body["error"]["code"] == "question_has_no_source"
    assert RecallItem.objects.count() == 0 and used(USER) == 0


def test_an_explanation_with_headings_and_images_still_makes_a_card(api, bank):
    bank.sources[QID] = src(explanation_md="## Rule\n\n![chart](http://x/y.png) Blocked for cars.")
    res = send(api)
    assert res.status_code == 201 and "##" not in res.json_body["cards"][0]["back_md"]


def test_the_banks_chapter_from_another_scheme_leaves_the_card_unsorted(api, bank):
    bank.sources[QID] = src(chapter_id=uuid.uuid4())
    res = send(api)
    assert res.status_code == 201 and res.json_body["cards"][0]["chapter"] is None


def test_a_chapter_she_chooses_wins_and_an_unknown_one_is_refused(api, bank, ids):
    bank.sources[QID] = src(chapter_id=uuid.UUID(ids["gst"]))
    ok = send(api, chapter_id=ids["residential"])
    assert ok.status_code == 201 and ok.json_body["cards"][0]["chapter"]["id"] == ids["residential"]
    other = uuid.uuid4()
    bank.sources[other] = src(question_id=other)
    bad = api.post(URL, {"question_id": str(other), "version_id": str(VID), "chapter_id": str(uuid.uuid4())})
    assert bad.status_code == 422 and bad.json_body["error"]["code"] == "unknown_chapter"


def test_the_undo_token_deletes_it_again(api, bank):
    bank.sources[QID] = src()
    res = send(api).json_body
    undone = api.post("/recall/cards/undo-delete/", {"undo_token": res["undo_token"]})
    assert undone.status_code == 200 and undone.json_body["status"] == "deleted"
    assert RecallCard.objects.get(pk=res["card_id"]).status == "deleted"


def test_a_full_plan_is_429_and_nothing_is_made(api, bank):
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=0)
    bank.sources[QID] = src()
    res = send(api)
    assert res.status_code == 429 and res.json_body["error"]["code"] == "quota_exceeded"
    assert RecallItem.objects.count() == 0 and used(USER) == 0


def test_bad_bodies_are_400(api, bank):
    assert api.post(URL, {"version_id": str(VID)}).status_code == 400
    assert api.post(URL, {"question_id": "nope", "version_id": str(VID)}).status_code == 400


def test_no_card_text_reaches_the_logs(api, bank, caplog):
    bank.sources[QID] = src()
    with caplog.at_level(logging.DEBUG):
        send(api)
    assert "motor cars" not in caplog.text and "17(5)" not in caplog.text


def test_the_bank_is_asked_for_the_signed_in_student_only(api, bank):
    bank.sources[QID] = src()
    send(api)
    assert bank.asked == [(str(USER), QID, VID)]


def test_another_student_gets_her_own_card_from_the_same_question(api, other_api, bank):
    bank.sources[QID] = src()
    a, b = send(api).json_body, other_api.post(URL, {"question_id": str(QID), "version_id": str(VID)}).json_body
    assert a["card_id"] != b["card_id"]
