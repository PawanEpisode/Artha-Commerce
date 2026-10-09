"""The review endpoints, the tick, the throttles and the promise that no card text reaches a log line."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from modules.recall.models import RecallReviewLog, RecallSession

from .w5 import ME, card

pytestmark = pytest.mark.django_db


def body(c, rating=3, at=None, **extra):
    return {
        "id": str(uuid.uuid4()),
        "card_id": str(c.id),
        "rating": rating,
        "reviewed_at": (at or timezone.now()).isoformat(),
        **extra,
    }


def test_review_roundtrip(api):
    c = card()
    payload = body(c, 3, duration_ms=3500, device_id="phone-1", tz_offset_min=330)
    res = api.post("/recall/reviews/", payload)
    assert res.status_code == 201
    out = res.json_body
    assert out["status"] == "applied" and out["merged"] is False and out["event_id"] == payload["id"]
    assert out["card"]["state_name"] == "learning" and out["card"]["rev"] == 2 and out["card"]["due_at"]
    again = api.post("/recall/reviews/", payload)
    assert again.status_code == 200 and again.json_body["status"] == "duplicate"
    assert RecallReviewLog.objects.filter(user_id=ME).count() == 1


@pytest.mark.parametrize(
    "bad", [{"rating": 0}, {"rating": 5}, {"mode": "sprint"}, {"reviewed_at": "yesterday"}, {"id": "x"}]
)
def test_bad_review_input_is_400(api, bad):
    assert api.post("/recall/reviews/", {**body(card()), **bad}).status_code == 400


def test_unknown_and_other_students_cards_are_404(api, other_api):
    mine = card()
    assert other_api.post("/recall/reviews/", body(mine)).status_code == 404
    assert api.post("/recall/reviews/", {**body(mine), "card_id": str(uuid.uuid4())}).status_code == 404


def test_batch_returns_a_result_per_event_and_the_changed_cards(api):
    a, b = card(), card()
    now = timezone.now()
    events = [
        body(a, 3, now - timedelta(minutes=5)),
        body(b, 4, now - timedelta(minutes=4)),
        {**body(a), "rating": 9},
        {**body(a), "card_id": str(uuid.uuid4())},
    ]
    res = api.post("/recall/reviews/batch/", {"events": events})
    assert res.status_code == 200
    out = res.json_body
    assert [r["status"] for r in out["results"][:2]] == ["applied", "applied"]
    assert sorted(r["reason"] for r in out["results"][2:]) == ["invalid_event", "unknown_card"]
    assert {c["id"] for c in out["cards"]} == {str(a.id), str(b.id)}


def test_a_batch_of_101_is_422(api):
    c = card()
    res = api.post("/recall/reviews/batch/", {"events": [body(c) for _ in range(101)]})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "batch_too_large"


def test_undo_over_the_api(api):
    c = card()
    payload = body(c)
    api.post("/recall/reviews/", payload)
    uid = str(uuid.uuid4())
    res = api.post("/recall/reviews/undo/", {"undo_id": uid, "voids_id": payload["id"]})
    assert res.status_code == 200 and res.json_body["card"]["state_name"] == "new"
    assert api.post("/recall/reviews/undo/", {"undo_id": uid, "voids_id": payload["id"]}).status_code == 200
    late = api.post("/recall/reviews/undo/", {"undo_id": str(uuid.uuid4()), "voids_id": payload["id"]})
    assert late.status_code == 409 and late.json_body["error"]["code"] == "not_undoable"
    assert (
        api.post("/recall/reviews/undo/", {"undo_id": str(uuid.uuid4()), "voids_id": str(uuid.uuid4())}).status_code
        == 404
    )


def test_sessions_open_close_and_the_summary(api):
    c = card()
    cid = str(uuid.uuid4())
    opened = api.post("/recall/sessions/", {"client_id": cid, "source": "today", "planned_count": 5})
    assert opened.status_code == 201
    sid = opened.json_body["id"]
    assert api.post("/recall/sessions/", {"client_id": cid, "source": "today"}).status_code == 200
    api.post("/recall/reviews/", body(c, 3, session_id=sid))
    closed = api.post(f"/recall/sessions/{sid}/close/")
    assert (
        closed.status_code == 200
        and closed.json_body["status"] == "closed"
        and closed.json_body["summary"]["reviewed"] == 1
    )
    assert api.post("/recall/sessions/", {"client_id": str(uuid.uuid4()), "source": "x"}).status_code == 422
    assert api.post(f"/recall/sessions/{uuid.uuid4()}/close/").status_code == 404


def test_other_students_sessions_cannot_be_closed(api, other_api):
    sid = other_api.post("/recall/sessions/", {"client_id": str(uuid.uuid4()), "source": "today"}).json_body["id"]
    assert api.post(f"/recall/sessions/{sid}/close/").status_code == 404
    assert RecallSession.objects.get(pk=sid).status == "open"


def test_rebalance_and_vacation_endpoints(api):
    assert api.post("/recall/catchup/rebalance/", {"days": 3}).json_body["moved"] == 0
    assert api.post("/recall/catchup/rebalance/", {"days": 99}).status_code == 400
    until = (timezone.now() + timedelta(days=3)).date().isoformat()
    res = api.put("/recall/vacation/", {"until": until})
    assert res.status_code == 200 and res.json_body["vacation_until"] == until
    assert api.put("/recall/vacation/", {"until": None}).json_body["vacation_until"] is None
    assert api.put("/recall/vacation/", {"until": "2020-01-01"}).status_code == 422


def test_the_tick_needs_the_secret_and_closes_idle_sessions_even_with_the_flag_off(api, flag_off, settings):
    settings.RECALL_TICK_SECRET = "s3cret"
    old = timezone.now() - timedelta(hours=2)
    s = RecallSession.objects.create(
        user_id=ME,
        client_id=uuid.uuid4(),
        source="today",
        started_at=old,
        last_event_at=old,
        tz="Asia/Kolkata",
        local_date=old.date(),
    )
    anon = Client()
    assert anon.post("/api/v1/recall/internal/tick/").status_code == 403
    assert anon.post("/api/v1/recall/internal/tick/", HTTP_X_RECALL_TICK_SECRET="wrong").status_code == 403
    ok = anon.post("/api/v1/recall/internal/tick/", HTTP_X_RECALL_TICK_SECRET="s3cret")
    assert ok.status_code == 200 and ok.json() == {"sessions_closed": 1}
    assert anon.get("/api/v1/recall/internal/tick/", HTTP_AUTHORIZATION="Bearer s3cret").json() == {
        "sessions_closed": 0
    }
    assert RecallSession.objects.get(pk=s.pk).status == "auto_closed"


def test_the_tick_refuses_everyone_when_no_secret_is_configured(settings):
    settings.RECALL_TICK_SECRET = ""
    assert Client().post("/api/v1/recall/internal/tick/", HTTP_X_RECALL_TICK_SECRET="").status_code == 403


def test_the_tick_is_not_open_to_browsers():
    import re

    from django.conf import settings

    assert not re.match(settings.CORS_URLS_REGEX, "/api/v1/recall/internal/tick/")
    assert re.match(settings.CORS_URLS_REGEX, "/api/v1/recall/reviews/")


def test_reviews_are_throttled_per_student_at_600_a_minute_but_cards_are_not_affected(api):
    ghost = {
        "id": str(uuid.uuid4()),
        "card_id": str(uuid.uuid4()),
        "rating": 3,
        "reviewed_at": timezone.now().isoformat(),
    }
    codes = [api.post("/recall/reviews/", {**ghost, "id": str(uuid.uuid4())}).status_code for _ in range(601)]
    assert set(codes[:600]) == {404} and codes[600] == 429
    assert api.get("/recall/cards/").status_code == 200


def test_the_review_scope_is_the_one_the_views_use():
    from modules.recall import views

    for cls in (
        views.ReviewSubmitView,
        views.ReviewBatchView,
        views.ReviewUndoView,
        views.SessionOpenView,
        views.SessionCloseView,
    ):
        assert cls.throttle_scope == "recall_review"
    for cls in (views.RebalanceView, views.VacationView):
        assert cls.throttle_scope == "recall_write"


SECRET = "ZZ-SECRET-CARD-TEXT-9931"


def test_no_card_text_in_any_log_line_or_event(api, caplog, django_capture_on_commit_callbacks):
    from core import events

    seen = []
    for name in ("recall_session_completed", "recall_leech_detected"):
        events.subscribe(name, lambda _n=name, **p: seen.append(repr(p)))
    caplog.set_level(logging.DEBUG)
    made = api.post(
        "/recall/cards/",
        {"client_id": str(uuid.uuid4()), "kind": "pointer", "fields": {"prompt_md": SECRET, "answer_md": SECRET + "!"}},
    )
    cid = made.json_body["cards"][0]["id"]
    with django_capture_on_commit_callbacks(execute=True):
        sid = api.post("/recall/sessions/", {"client_id": str(uuid.uuid4()), "source": "today"}).json_body["id"]
        first = {
            "id": str(uuid.uuid4()),
            "card_id": cid,
            "rating": 1,
            "reviewed_at": timezone.now().isoformat(),
            "session_id": sid,
        }
        api.post("/recall/reviews/", first)
        api.post("/recall/reviews/batch/", {"events": [{**first, "id": str(uuid.uuid4()), "rating": 3}]})
        api.post("/recall/reviews/undo/", {"undo_id": str(uuid.uuid4()), "voids_id": first["id"]})
        api.post("/recall/catchup/rebalance/", {})
        api.post(f"/recall/sessions/{sid}/close/")
    events.clear()
    assert seen and SECRET not in caplog.text and not any(SECRET in s for s in seen)
