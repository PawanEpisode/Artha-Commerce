"""R2-W4 B: "these are my own words" (FR-F15-21): a selection card is private until she says so, and can say it back."""

from __future__ import annotations

import uuid

import pytest

from modules.recall.models import RecallAuditLog, RecallItem

from .support import made
from .w22 import card_of, deck_with_student

pytestmark = pytest.mark.django_db


def pick(api, text="Remember the three tests of control", origin="note_highlight"):
    res = api.post(
        "/recall/cards/from-selection/",
        {
            "client_id": uuid.uuid4().hex,
            "origin": origin,
            "selection_text": text,
            "source": {"module": "notes", "object_id": "mark-1", "locator": {}},
        },
    )
    assert res.status_code == 201, res.json_body
    return res.json_body["card_id"]


def attest(api, card_id, own_words=True):
    return api.post(f"/recall/cards/{card_id}/attest/", {"own_words": own_words})


def test_a_selection_card_starts_private_and_says_a_statement_applies(api):
    card = api.get(f"/recall/cards/{pick(api)}/").json_body
    assert card["shareable"] is False
    assert card["attestation"] == {"required": True, "attested": False, "attested_at": None}


def test_saying_the_words_are_hers_makes_it_shareable_and_keeps_the_time(api):
    card_id = pick(api)
    res = attest(api, card_id)
    body = res.json_body
    assert res.status_code == 200 and body["changed"] is True and body["shareable"] is True
    assert body["required"] is True and body["attested"] is True and body["attested_at"].endswith("Z")
    detail = api.get(f"/recall/cards/{card_id}/").json_body
    assert detail["shareable"] is True and detail["attestation"]["attested"] is True
    audit = RecallAuditLog.objects.get(action="attest_own_words")
    assert audit.target_kind == "item" and audit.detail == {"v": 1, "own_words": True, "origin": "selection"}
    assert RecallItem.objects.get(origin="selection").shareable_attested_at is not None


def test_it_is_idempotent_and_writes_one_audit_row(api):
    card_id = pick(api)
    first = attest(api, card_id).json_body
    again = attest(api, card_id)
    assert again.status_code == 200 and again.json_body["changed"] is False
    assert again.json_body["attested_at"] == first["attested_at"]
    assert RecallAuditLog.objects.filter(action="attest_own_words").count() == 1


def test_she_can_take_it_back(api):
    card_id = pick(api)
    attest(api, card_id)
    res = attest(api, card_id, own_words=False)
    assert (
        res.json_body["changed"] is True and res.json_body["shareable"] is False and res.json_body["attested"] is False
    )
    assert res.json_body["attested_at"] is None
    assert attest(api, card_id, own_words=False).json_body["changed"] is False
    assert RecallAuditLog.objects.filter(action="attest_own_words").count() == 2


def test_a_solution_and_a_mistake_card_can_be_attested_too(api):
    for origin in ("solution_text", "question_review"):
        assert attest(api, pick(api, text=f"Remember rule for {origin}", origin=origin)).json_body["attested"] is True


def test_a_manual_card_needs_no_statement(api):
    card = made(api)
    assert api.get(f"/recall/cards/{card['id']}/").json_body["attestation"]["required"] is False
    res = attest(api, card["id"])
    assert res.status_code == 422 and res.json_body["error"]["code"] == "attestation_not_needed"


def test_an_imported_card_cannot_be_attested(api):
    res = api.post("/recall/cards/import/", {"client_id": uuid.uuid4().hex, "text": "One? :: two"})
    card_id = res.json_body["rows"][0]["card_id"]
    assert attest(api, card_id).status_code == 422


def test_a_platform_card_cannot_be_attested(api):
    _, items, _ = deck_with_student(2)
    res = attest(api, card_of(items[0]).id)
    assert res.status_code == 422 and res.json_body["error"]["code"] == "attestation_not_needed"


def test_another_students_card_is_a_404_and_changes_nothing(api, other_api):
    card_id = pick(api)
    assert attest(other_api, card_id).status_code == 404
    assert RecallItem.objects.get(origin="selection").shareable is False


def test_a_deleted_card_is_a_404(api):
    card_id = pick(api)
    api.delete(f"/recall/cards/{card_id}/")
    assert attest(api, card_id).status_code == 404


def test_the_body_must_say_yes_or_no(api):
    assert api.post(f"/recall/cards/{pick(api)}/attest/", {}).status_code == 400
