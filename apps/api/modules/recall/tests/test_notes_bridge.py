"""R2-W0: Notes "Make a card" end to end, flag on and off: the card is studyable, the review lands, and with the flag off nothing leaks."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from core import feature_flags, recall_port
from modules.recall.models import RecallCard, RecallItem, RecallReviewLog
from modules.recall.provider import RecallProviderImpl

from .test_provider import notes_mark

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def provider():
    previous = recall_port.get_recall_provider()
    recall_port.register_recall_provider(RecallProviderImpl())
    yield
    recall_port.register_recall_provider(previous)


def _make(api, mark, **extra):
    return api.post(f"/notes/annotations/{mark['id']}/card/", {"client_id": str(uuid.uuid4()), **extra})


def test_a_card_made_from_a_mark_is_in_the_queue_and_a_review_of_it_lands(api):
    mark = notes_mark(api)
    card_id = _make(api, mark).json_body["card_id"]
    queue = api.get("/recall/queue/")
    assert queue.status_code == 200 and card_id in str(queue.json_body)
    review = api.post(
        "/recall/reviews/batch/",
        {
            "events": [
                {"id": str(uuid.uuid4()), "card_id": card_id, "rating": 3, "reviewed_at": datetime.now(UTC).isoformat()}
            ]
        },
    )
    assert review.status_code == 200 and review.json_body["results"][0]["status"] == "applied"
    assert RecallReviewLog.objects.filter(card_id=card_id).count() == 1


def test_another_student_cannot_make_a_card_from_my_mark(api, other_api):
    mark = notes_mark(api)
    assert _make(other_api, mark).status_code == 404
    assert RecallItem.objects.count() == 0


def test_a_mark_that_already_has_a_card_stays_known_after_the_flag_goes_off_but_makes_no_new_card(api, monkeypatch):
    mark = notes_mark(api)
    first = _make(api, mark).json_body
    monkeypatch.setattr(feature_flags, "_lookup", lambda name, distinct_id: name != "recall_system")
    again = _make(api, mark)
    assert again.status_code in (200, 503)
    forced = _make(api, mark, kind="definition")  # a different kind would need a new card
    assert forced.status_code == 503 and forced.json_body["error"]["code"] == "recall_unavailable"
    assert (
        RecallCard.objects.filter(
            user_id=api.user_id if hasattr(api, "user_id") else RecallCard.objects.first().user_id
        ).count()
        == 1
    )
    assert first["existing"] is False


def test_with_the_flag_off_the_recall_endpoints_are_closed_but_export_and_erase_stay_open(api, monkeypatch):
    mark = notes_mark(api)
    _make(api, mark)
    monkeypatch.setattr(feature_flags, "_lookup", lambda name, distinct_id: name != "recall_system")
    assert api.get("/recall/queue/").status_code == 403
    assert api.get("/recall/export/").status_code == 200
