import uuid

import pytest

from modules.recall.models import RecallReport

from .factories import USER, make_item
from .w11 import published_deck

pytestmark = pytest.mark.django_db


def url(item):
    return f"/recall/items/{item.id}/report/"


def test_a_student_reports_an_item_in_a_live_deck_and_a_second_tap_is_a_noop(api):
    deck, items, version = published_deck(2)
    first = api.post(url(items[0]), {"reason": "wrong", "note": "Section is 17(5)"})
    assert first.status_code in (200, 201)
    second = api.post(url(items[0]), {"reason": "outdated"})
    assert second.status_code in (200, 201)
    rows = RecallReport.objects.filter(reporter_user_id=USER)
    assert rows.count() == 1
    r = rows.get()
    assert r.target_kind == "item" and r.target_id == items[0].id and r.status == "open" and r.reason == "wrong"
    items[0].refresh_from_db()
    assert r.item_version_id == items[0].live_version_id


def test_reasons_are_limited_and_the_note_has_a_cap(api):
    _, items, _ = published_deck(1)
    assert api.post(url(items[0]), {"reason": "abusive"}).status_code == 400
    assert api.post(url(items[0]), {"reason": "wrong", "note": "x" * 501}).status_code == 400
    assert api.post(url(items[0]), {}).status_code == 400


def test_a_student_cannot_report_what_she_cannot_see(api):
    own = make_item(owner=uuid.uuid4())  # someone's own card
    assert api.post(url(own), {"reason": "wrong"}).status_code == 404
    assert api.post(f"/recall/items/{uuid.uuid4()}/report/", {"reason": "wrong"}).status_code == 404
    assert RecallReport.objects.count() == 0


def test_a_closed_report_can_be_filed_again(api):
    _, items, _ = published_deck(1)
    api.post(url(items[0]), {"reason": "wrong"})
    RecallReport.objects.update(status="actioned")
    api.post(url(items[0]), {"reason": "outdated"})
    assert RecallReport.objects.count() == 2 and RecallReport.objects.filter(status="open").count() == 1
