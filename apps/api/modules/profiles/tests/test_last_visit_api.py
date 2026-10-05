import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from modules.profiles import services
from modules.profiles.models import LastVisit, Profile

from .conftest import USER

URL = "/api/v1/me/last-visit/"


def beacon(token: str | None, **body):
    """What `navigator.sendBeacon` sends: text/plain JSON, the token in the body, no Authorization header."""
    payload = {"path": "/app/tracker", "search": "", **body}
    if token is not None:
        payload["t"] = token
    return Client().post(URL, data=json.dumps(payload), content_type="text/plain;charset=UTF-8")


@pytest.fixture
def student(api):
    api.get("/me/")  # lazily creates the profile
    return api


def stored():
    return LastVisit.objects.get(pk=USER)


def test_a_bearer_write_is_stored_and_shows_in_the_bootstrap(student):
    res = student.post("/me/last-visit/", {"path": "/app/syllabus/fin-acc/ch-3", "search": ""})
    assert res.status_code == 204
    visit = student.get("/me/").json_body["last_visit"]
    assert visit["path"] == "/app/syllabus/fin-acc/ch-3" and visit["at"]


def test_put_works_like_post(student):
    assert student.put("/me/last-visit/", {"path": "/app/revision"}).status_code == 204
    assert stored().path == "/app/revision"


def test_a_beacon_with_the_token_in_the_body_is_accepted(student, make_token):
    assert beacon(make_token(sub=USER)).status_code == 204
    assert stored().path == "/app/tracker"


def test_a_beacon_without_a_valid_token_is_401_and_writes_nothing(student, make_token):
    assert beacon(None).status_code == 401
    assert beacon("not-a-jwt").status_code == 401
    assert not LastVisit.objects.exists()


def test_the_body_token_works_only_on_this_endpoint(student, make_token):
    res = Client().post(
        "/api/v1/me/avatar/preset/",
        data=json.dumps({"key": "p01", "t": make_token(sub=USER)}),
        content_type="text/plain",
    )
    assert res.status_code == 401


def test_the_token_decides_who_the_visit_belongs_to(student, make_token, other_api):
    other_api.get("/me/")
    assert beacon(make_token(sub="9a1e7c52-1a5b-4d6e-8c3f-2b7d4e5f6a70"), path="/app/focus").status_code == 204
    assert not LastVisit.objects.filter(pk=USER).exists()
    assert LastVisit.objects.get(pk="9a1e7c52-1a5b-4d6e-8c3f-2b7d4e5f6a70").path == "/app/focus"


def test_unauthenticated_is_401():
    assert Client().post(URL, data=json.dumps({"path": "/app"}), content_type="application/json").status_code == 401


@pytest.mark.parametrize("path", ["/app/account", "/app/onboarding", "/login", "https://evil.com", "/app/../x", ""])
def test_pages_that_are_not_restorable_are_400(student, path):
    res = student.post("/me/last-visit/", {"path": path})
    assert res.status_code == 400
    assert not LastVisit.objects.exists()
    if path:
        assert res.json_body["error"]["code"] == "path_not_restorable"


def test_malformed_bodies_are_400(student):
    assert student.post("/me/last-visit/", {}).status_code == 400
    assert student.post("/me/last-visit/", {"path": "/app", "search": "x" * 201}).status_code == 400
    res = student.c.post(URL, data="[1, 2]", content_type="text/plain")
    assert res.status_code == 400


def test_the_query_string_is_reduced_to_the_keys_the_page_knows(student):
    student.post("/me/last-visit/", {"path": "/app/tracker/reports", "search": "?range=7d&from=2026-01-01&x=1"})
    assert stored().search == "range=7d"


def test_a_body_over_one_kilobyte_is_413_before_it_is_read(student):
    res = student.post("/me/last-visit/", {"path": "/app", "search": "a" * 200, "pad": "b" * 2000})
    assert res.status_code == 413


def test_writes_are_throttled(student):
    codes = [student.post("/me/last-visit/", {"path": "/app/revision"}).status_code for _ in range(21)]
    assert codes[:20] == [204] * 20 and codes[20] == 429


def test_with_personalization_off_it_is_403(student, flag_off):
    flag_off("personalization")
    assert student.post("/me/last-visit/", {"path": "/app/revision"}).status_code == 403


def test_a_late_beacon_after_account_deletion_does_not_bring_a_row_back(student):
    Profile.objects.filter(pk=USER).delete()
    assert student.post("/me/last-visit/", {"path": "/app/revision"}).status_code == 204
    assert not LastVisit.objects.exists()


# --- the service rule, with a controlled clock -------------------------------------------------------------------


def test_the_same_page_within_a_minute_is_not_written_again(student):
    t0 = timezone.now()
    assert services.record_visit(USER, "/app/tracker", now=t0) is True
    assert services.record_visit(USER, "/app/tracker", now=t0 + timedelta(seconds=30)) is False
    assert stored().visited_at == t0


def test_the_same_page_after_a_minute_refreshes_the_time(student):
    t0 = timezone.now()
    services.record_visit(USER, "/app/tracker", now=t0)
    later = t0 + timedelta(seconds=61)
    assert services.record_visit(USER, "/app/tracker", now=later) is True
    assert stored().visited_at == later


def test_a_different_page_is_written_at_once(student):
    t0 = timezone.now()
    services.record_visit(USER, "/app/tracker", now=t0)
    assert services.record_visit(USER, "/app/focus", now=t0 + timedelta(seconds=1)) is True
    assert stored().path == "/app/focus"
    assert LastVisit.objects.count() == 1
