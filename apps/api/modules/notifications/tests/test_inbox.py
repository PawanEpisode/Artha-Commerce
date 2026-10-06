"""GET inbox/ and POST inbox/read/: the list, the unread count, paging and marking read (W3.1)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from modules.notifications.models import Notification, Preference
from modules.notifications.selectors import inbox as selector
from modules.notifications.services import inbox as service

pytestmark = pytest.mark.django_db
BASE = "/api/v1/notifications/inbox/"
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
OTHER = uuid.uuid4()
T0 = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)


def make(user=USER, *, minutes=0, category="timer", read=False, expires=None, title="Round 1 done"):
    n = Notification.objects.create(
        user_id=user,
        category=category,
        event="timer_end",
        dedupe_key=f"k:{uuid.uuid4().hex}",
        title=title,
        body="25 minutes.",
        deep_link="/app/focus",
        priority=0,
        read_at=T0 if read else None,
        expires_at=expires,
    )
    Notification.objects.filter(id=n.id).update(created_at=T0 + timedelta(minutes=minutes))
    n.refresh_from_db()
    return n


def get(client, **params):
    return client.get(BASE, params)


def mark(client, body):
    return client.post(f"{BASE}read/", body, content_type="application/json")


# --- list ----------------------------------------------------------------------------------------------------------
def test_requires_sign_in(client):
    assert client.get(BASE).status_code in (401, 403)
    assert client.post(f"{BASE}read/", {}, content_type="application/json").status_code in (401, 403)


def test_an_empty_inbox(auth_client):
    r = get(auth_client)
    assert r.status_code == 200
    assert r.json() == {"results": [], "next_cursor": None, "unread_count": 0}


def test_lists_newest_first_with_the_item_shape_and_the_unread_count(auth_client):
    old = make(minutes=0, title="old", read=True)
    new = make(minutes=5, title="new")
    body = get(auth_client).json()
    assert [i["id"] for i in body["results"]] == [str(new.id), str(old.id)]
    assert body["unread_count"] == 1
    assert body["results"][0] == {
        "id": str(new.id),
        "category": "timer",
        "category_label": "Timer alerts",
        "title": "new",
        "body": "25 minutes.",
        "deep_link": "/app/focus",
        "read": False,
        "created_at": new.created_at.isoformat(),
    }
    assert body["results"][1]["read"] is True


def test_the_unread_count_covers_every_unread_item_not_only_the_page(auth_client):
    for i in range(5):
        make(minutes=i)
    body = get(auth_client, limit=2).json()
    assert len(body["results"]) == 2 and body["unread_count"] == 5


def test_only_the_students_own_items_show(auth_client):
    mine = make()
    make(OTHER)
    body = get(auth_client).json()
    assert [i["id"] for i in body["results"]] == [str(mine.id)] and body["unread_count"] == 1


def test_expired_items_are_left_out_and_a_future_expiry_stays(auth_client):
    now = timezone.now()
    make(expires=now - timedelta(minutes=1))
    keep = make(minutes=1, expires=now + timedelta(hours=1))
    body = get(auth_client).json()
    assert [i["id"] for i in body["results"]] == [str(keep.id)] and body["unread_count"] == 1


def test_a_category_switched_off_for_the_inbox_is_hidden_from_list_and_count(auth_client):
    make(category="revision")
    shown = make(minutes=1, category="timer")
    Preference.objects.create(user_id=USER, category="revision", channel="inbox", enabled=False)
    body = get(auth_client).json()
    assert [i["id"] for i in body["results"]] == [str(shown.id)] and body["unread_count"] == 1


def test_a_push_switch_does_not_hide_the_inbox_item(auth_client):
    n = make(category="revision")
    Preference.objects.create(user_id=USER, category="revision", channel="push", enabled=False)
    assert [i["id"] for i in get(auth_client).json()["results"]] == [str(n.id)]


def test_the_test_push_has_no_switch_and_always_shows(auth_client):
    n = make(category="system")
    body = get(auth_client).json()
    assert body["results"][0]["id"] == str(n.id) and body["results"][0]["category_label"] == "Test"


# --- paging --------------------------------------------------------------------------------------------------------
def test_cursor_paging_walks_every_item_once_in_order(auth_client):
    made = [make(minutes=i) for i in range(7)]
    expected = [str(n.id) for n in reversed(made)]
    seen, cursor = [], None
    for _ in range(10):
        body = get(auth_client, limit=3, **({"cursor": cursor} if cursor else {})).json()
        seen += [i["id"] for i in body["results"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == expected


def test_items_with_the_same_timestamp_are_not_skipped_or_repeated(auth_client):
    made = [make(minutes=0) for _ in range(5)]
    seen, cursor = [], None
    while True:
        body = get(auth_client, limit=2, **({"cursor": cursor} if cursor else {})).json()
        seen += [i["id"] for i in body["results"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert sorted(seen) == sorted(str(n.id) for n in made) and len(seen) == 5


def test_the_last_page_has_no_cursor(auth_client):
    make()
    assert get(auth_client, limit=1).json()["next_cursor"] is None


def test_the_inbox_never_goes_past_the_newest_fifty(auth_client):
    for i in range(55):
        make(minutes=i)
    seen, cursor = [], None
    while True:
        body = get(auth_client, limit=20, **({"cursor": cursor} if cursor else {})).json()
        seen += [i["id"] for i in body["results"]]
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == selector.INBOX_CAP == 50 and len(set(seen)) == 50
    assert Notification.objects.filter(user_id=USER).count() == 55


def test_a_page_of_fifty_ends_there(auth_client):
    for i in range(60):
        make(minutes=i)
    body = get(auth_client, limit=50).json()
    assert len(body["results"]) == 50 and body["next_cursor"] is None


@pytest.mark.parametrize("cursor", ["!!!", "bm90LWEtY3Vyc29y", "x" * 201])
def test_a_bad_cursor_is_a_400(auth_client, cursor):
    assert get(auth_client, cursor=cursor).status_code == 400


def test_a_blank_cursor_means_the_first_page(auth_client):
    make()
    assert len(get(auth_client, cursor="").json()["results"]) == 1


def test_a_cursor_that_claims_to_be_past_the_cap_is_rejected(auth_client):
    import base64

    n = make()
    forged = base64.urlsafe_b64encode(f"{n.created_at.isoformat()}|{n.id}|50".encode()).decode()
    r = get(auth_client, cursor=forged)
    assert r.status_code == 400 and r.json()["error"]["code"] == "bad_cursor"


@pytest.mark.parametrize("limit", [0, 51, "x", -1])
def test_a_bad_limit_is_a_400(auth_client, limit):
    assert get(auth_client, limit=limit).status_code == 400


def test_a_cursor_cannot_read_another_students_rows(auth_client):
    theirs = make(OTHER)
    mine = make(minutes=-10)
    import base64

    forged = base64.urlsafe_b64encode(f"{(T0 + timedelta(minutes=5)).isoformat()}|{theirs.id}|0".encode()).decode()
    assert [i["id"] for i in get(auth_client, cursor=forged).json()["results"]] == [str(mine.id)]


# --- mark read -----------------------------------------------------------------------------------------------------
def test_mark_some_read_and_the_count_drops(auth_client):
    a, b, c = make(minutes=0), make(minutes=1), make(minutes=2)
    r = mark(auth_client, {"ids": [str(a.id), str(b.id)]})
    assert r.status_code == 200 and r.json() == {"unread_count": 1}
    a.refresh_from_db(), b.refresh_from_db(), c.refresh_from_db()
    assert a.read_at and b.read_at and c.read_at is None


def test_mark_all_read(auth_client):
    make(), make(minutes=1)
    other = make(OTHER)
    r = mark(auth_client, {"all": True})
    assert r.json() == {"unread_count": 0}
    assert Notification.objects.filter(user_id=USER, read_at__isnull=True).count() == 0
    other.refresh_from_db()
    assert other.read_at is None


def test_marking_again_is_harmless_and_keeps_the_first_timestamp(auth_client):
    n = make()
    mark(auth_client, {"ids": [str(n.id)]})
    n.refresh_from_db()
    first = n.read_at
    assert mark(auth_client, {"ids": [str(n.id)]}).json() == {"unread_count": 0}
    n.refresh_from_db()
    assert n.read_at == first


def test_another_students_id_is_ignored_and_untouched(auth_client):
    mine, theirs = make(), make(OTHER)
    r = mark(auth_client, {"ids": [str(theirs.id), str(uuid.uuid4())]})
    assert r.status_code == 200 and r.json() == {"unread_count": 1}
    theirs.refresh_from_db()
    assert theirs.read_at is None
    mine.refresh_from_db()
    assert mine.read_at is None


def test_hidden_and_expired_items_are_not_touched_by_mark_all(auth_client):
    hidden = make(category="revision")
    expired = make(expires=timezone.now() - timedelta(minutes=1))
    Preference.objects.create(user_id=USER, category="revision", channel="inbox", enabled=False)
    mark(auth_client, {"all": True})
    hidden.refresh_from_db(), expired.refresh_from_db()
    assert hidden.read_at is None and expired.read_at is None


@pytest.mark.parametrize(
    "body",
    [{}, {"ids": []}, {"all": False}, {"ids": ["not-a-uuid"]}, {"ids": [str(uuid.uuid4())], "all": True}, {"ids": "x"}],
)
def test_a_bad_body_is_a_400(auth_client, body):
    assert mark(auth_client, body).status_code == 400


def test_more_than_fifty_ids_is_a_400(auth_client):
    assert mark(auth_client, {"ids": [str(uuid.uuid4()) for _ in range(51)]}).status_code == 400


def test_the_service_stamps_the_time_it_is_given():
    n = make()
    later = T0 + timedelta(hours=1)
    assert service.mark_read(USER, ids=[n.id], now=later) == 1
    n.refresh_from_db()
    assert n.read_at == later
    assert service.mark_read(USER, ids=[n.id], now=later) == 0


# --- gates and budgets ---------------------------------------------------------------------------------------------
def test_both_endpoints_are_behind_the_environment_switch_and_the_ui_flag(auth_client, settings, monkeypatch):
    n = make()
    settings.NOTIFICATIONS_ENABLED = False
    for r in (get(auth_client), mark(auth_client, {"all": True})):
        assert r.status_code == 403 and r.json()["error"]["code"] == "notifications_disabled"
    settings.NOTIFICATIONS_ENABLED = True
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    assert get(auth_client).status_code == 403
    assert mark(auth_client, {"all": True}).status_code == 403
    n.refresh_from_db()
    assert n.read_at is None


def test_the_list_draws_on_the_read_budget_and_marking_on_the_write_budget(auth_client, monkeypatch):
    from rest_framework.throttling import ScopedRateThrottle

    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "notifications_read", "2/min")
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "notifications_write", "2/min")
    assert [get(auth_client).status_code for _ in range(3)] == [200, 200, 429]
    assert [mark(auth_client, {"all": True}).status_code for _ in range(3)] == [200, 200, 429]


def test_the_list_runs_a_fixed_number_of_queries(auth_client, django_assert_max_num_queries):
    for i in range(10):
        make(minutes=i)
    with django_assert_max_num_queries(6):
        assert get(auth_client).status_code == 200


# --- erasure and export (FR-N25) -----------------------------------------------------------------------------------
def test_erasure_removes_the_inbox_and_export_lists_it():
    from modules.notifications.selectors import export
    from modules.notifications.services import erasure

    make(), make(minutes=1), make(OTHER)
    assert len(export.export_all(USER)["notifications"]) == 2
    assert erasure.delete_all_for_user(USER)["notifications"] == 2
    assert Notification.objects.filter(user_id=USER).count() == 0
    assert Notification.objects.filter(user_id=OTHER).count() == 1
