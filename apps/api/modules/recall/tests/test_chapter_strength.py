"""R2-W3 B: recall strength on a chapter page (FR-F15-65): the endpoint, its numbers, isolation and its cost."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from modules.recall import selectors
from modules.recall.domain.fsrs6 import DEFAULT_WEIGHTS, retrievability
from modules.recall.models import RecallCard
from modules.recall.services import reviews

from .w5 import ME, ev
from .w6 import library

pytestmark = pytest.mark.django_db


def strength(api, chapter, **q):
    qs = "".join(f"&{k}={v}" for k, v in q.items())
    res = api.get(f"/recall/chapters/{chapter}/strength/?{qs.lstrip('&')}")
    assert res.status_code == 200, res.json_body
    return res.json_body


def test_the_strength_is_the_mean_predicted_recall_and_the_count_due(api):
    ch = uuid.uuid4()
    now = timezone.now()
    library(8, shape=lambda i: "due" if i < 6 else "later", chapter_id=ch, now=now)
    body = strength(api, ch)
    assert (body["chapter_id"], body["cards"], body["due"]) == (str(ch), 8, 6)
    expected = []
    for c in RecallCard.objects.filter(user_id=ME, chapter_id=ch):
        elapsed = (now - c.last_review_at).total_seconds() / 86400
        expected.append(retrievability(c.stability, elapsed, DEFAULT_WEIGHTS[20]))
    assert body["strength"] == pytest.approx(sum(expected) / len(expected), abs=1e-3)
    assert body["percent"] == round(body["strength"] * 100)
    assert 0 < body["strength"] < 1


def test_new_cards_count_but_do_not_pull_the_average(api):
    ch = uuid.uuid4()
    library(5, shape=lambda i: "new", chapter_id=ch)
    body = strength(api, ch)
    assert (body["cards"], body["due"], body["strength"], body["percent"]) == (5, 0, None, None)


def test_a_chapter_without_cards_is_empty_not_missing(api):
    ch = uuid.uuid4()
    assert strength(api, ch) == {"chapter_id": str(ch), "cards": 0, "due": 0, "strength": None, "percent": None}


def test_the_strength_goes_up_after_a_review(api):
    ch = uuid.uuid4()
    now = timezone.now()
    cards = library(6, shape=lambda i: "due", chapter_id=ch, now=now)
    before = strength(api, ch)
    for c in cards:
        reviews.submit_review(ME, ev(c, 3, now - timedelta(seconds=30)), now=now)
    after = strength(api, ch)
    assert after["strength"] > before["strength"] and after["due"] < before["due"]


def test_only_her_active_cards_in_that_chapter_count(api):
    ch, other_ch = uuid.uuid4(), uuid.uuid4()
    mine = library(4, shape=lambda i: "due", chapter_id=ch)
    library(3, shape=lambda i: "due", chapter_id=other_ch)
    library(5, shape=lambda i: "due", chapter_id=ch, user=uuid.uuid4())  # someone else's
    RecallCard.objects.filter(pk=mine[0].pk).update(status="suspended")
    RecallCard.objects.filter(pk=mine[1].pk).update(status="deleted", deleted_at=timezone.now())
    assert strength(api, ch)["cards"] == 2


def test_the_read_costs_the_same_number_of_queries_for_two_cards_or_two_hundred(api):
    small, large = uuid.uuid4(), uuid.uuid4()
    library(2, shape=lambda i: "due", chapter_id=small)
    library(200, shape=lambda i: ("due", "later", "new")[i % 3], chapter_id=large)
    strength(api, small)  # warm anything cached
    with CaptureQueriesContext(connection) as few:
        strength(api, small)
    with CaptureQueriesContext(connection) as many:
        strength(api, large)
    assert len(many) == len(few) and len(many) <= 12  # one pass over her cards in the chapter, nothing per card


def test_a_bad_time_zone_is_refused_and_a_good_one_accepted(api):
    ch = uuid.uuid4()
    assert api.get(f"/recall/chapters/{ch}/strength/?tz=Mars/Olympus").status_code == 422
    assert strength(api, ch, tz="Asia/Kolkata")["cards"] == 0


def test_another_students_token_sees_only_her_own_cards(api, other_api):
    ch = uuid.uuid4()
    library(4, shape=lambda i: "due", chapter_id=ch)
    assert strength(api, ch)["cards"] == 4 and strength(other_api, ch)["cards"] == 0


def test_the_selector_has_the_same_numbers(api):
    ch = uuid.uuid4()
    library(6, shape=lambda i: "due", chapter_id=ch)
    row = selectors.chapter_strength(ME, ch, now=timezone.now())
    assert (row.cards, row.due) == (6, 6) and row.strength == pytest.approx(strength(api, ch)["strength"], abs=1e-3)
