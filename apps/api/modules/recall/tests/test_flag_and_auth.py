import uuid

import pytest
from django.test import Client

from modules.recall.views import RECALL_OPEN_PATHS

pytestmark = pytest.mark.django_db

CARD = str(uuid.uuid4())
URLS = [
    ("get", "/recall/cards/"),
    ("post", "/recall/cards/"),
    ("post", "/recall/cards/from-selection/"),
    ("post", "/recall/cards/undo-delete/"),
    ("post", "/recall/cards/bulk/"),
    ("get", f"/recall/cards/{CARD}/"),
    ("patch", f"/recall/cards/{CARD}/"),
    ("delete", f"/recall/cards/{CARD}/"),
    ("get", f"/recall/cards/{CARD}/reviews/"),
    *[("post", f"/recall/cards/{CARD}/{slug}/") for slug in ("suspend", "unsuspend", "bury", "reset", "recheck-ok")],
    ("post", "/recall/reviews/"),
    ("post", "/recall/reviews/batch/"),
    ("post", "/recall/reviews/undo/"),
    ("post", "/recall/sessions/"),
    ("post", f"/recall/sessions/{CARD}/close/"),
    ("post", "/recall/catchup/rebalance/"),
    ("put", "/recall/vacation/"),
    ("get", "/recall/today/"),
    ("get", "/recall/queue/"),
    ("get", "/recall/pack/"),
    ("get", "/recall/forgotten/"),
    *[("get", f"/recall/stats/{name}/") for name in ("summary", "retention", "forecast", "chapters")],
    ("get", "/recall/settings/"),
    ("put", "/recall/settings/"),
    ("get", "/recall/decks/library/"),
    ("get", "/recall/decks/subscribed/"),
    ("get", f"/recall/decks/{CARD}/"),
    ("post", f"/recall/decks/{CARD}/subscribe/"),
    ("post", f"/recall/subscriptions/{CARD}/unsubscribe/"),
    ("post", f"/recall/subscriptions/{CARD}/resubscribe/"),
    ("post", f"/recall/items/{CARD}/report/"),
    ("get", "/recall/export/"),
    ("get", "/recall/export/cards.csv"),
    ("get", "/recall/export/reviews.csv"),
    ("post", "/recall/erase/"),
]
TICK = "/recall/internal/tick/"  # authenticated by a shared secret, open whatever the flag says (tested in test_reviews_api)


def call(client, method, path):
    return client.generic(method.upper(), f"/api/v1{path}", "{}", content_type="application/json")


@pytest.mark.parametrize(("method", "path"), URLS)
def test_every_recall_url_needs_a_token(method, path):
    assert call(Client(), method, path).status_code == 401


@pytest.mark.parametrize(("method", "path"), URLS)
def test_every_recall_url_is_403_feature_disabled_with_the_flag_off(api, flag_off, method, path):
    if path in RECALL_OPEN_PATHS:
        return  # W11: data export and delete-all stay open (D4)
    res = call(api.c, method, path)
    assert res.status_code == 403 and res.json()["error"]["code"] == "feature_disabled"


def test_export_and_erase_stay_open_with_the_flag_off(api, flag_off):
    """D4: a rollout switch must never block the student's data rights (DPDP)."""
    assert RECALL_OPEN_PATHS == (
        "/recall/export/",
        "/recall/export/cards.csv",
        "/recall/export/reviews.csv",
        "/recall/erase/",
    )
    for path in RECALL_OPEN_PATHS:
        res = api.c.generic(
            "POST" if path.endswith("erase/") else "GET", f"/api/v1{path}", "{}", content_type="application/json"
        )
        assert res.status_code not in (401, 403), path


def test_the_flag_fails_closed_without_posthog(api, monkeypatch):
    from core import feature_flags

    monkeypatch.undo()  # drop the autouse "on" answer: no PostHog key in tests means unknown
    feature_flags.clear_flag_cache()
    assert api.get("/recall/cards/").status_code == 403


def test_nothing_is_written_with_the_flag_off(api, flag_off):
    assert (
        api.post("/recall/cards/", {"client_id": str(uuid.uuid4()), "kind": "pointer", "fields": {}}).status_code == 403
    )
    from modules.recall.models import RecallItem

    assert RecallItem.objects.count() == 0


def test_every_recall_route_is_in_the_matrix():
    from modules.recall import urls

    assert len(urls.urlpatterns) == len({path.replace(CARD, "<id>") for _, path in URLS}) + 1  # + the tick


def test_throttle_scopes_exist():
    from django.conf import settings

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert (rates["recall_review"], rates["recall_write"], rates["recall_export"]) == ("600/min", "120/min", "6/hour")
