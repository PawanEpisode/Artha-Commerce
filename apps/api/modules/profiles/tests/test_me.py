"""GET/PATCH /me/: the bootstrap that fills the header, the gate and the destination in one request."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from modules.profiles.models import Onboarding, Profile
from modules.profiles.tests.conftest import USER

pytestmark = pytest.mark.django_db


def test_health_is_public(client):
    assert client.get("/api/v1/health/").json() == {"status": "ok"}


def test_ready_checks_database(client):
    assert client.get("/api/v1/health/ready/").json()["database"] == "up"


def test_me_requires_auth(client):
    res = client.get("/api/v1/me/")
    assert res.status_code == 401
    assert res.json()["error"]["code"] in {"not_authenticated", "authentication_failed"}


def test_me_rejects_bad_token(client):
    res = client.get("/api/v1/me/", HTTP_AUTHORIZATION="Bearer nonsense")
    assert res.status_code == 401


def test_the_bootstrap_creates_the_profile_and_onboarding_rows_lazily(api):
    body = api.get("/me/").json_body
    assert body["id"] == USER and body["email"] == "student@example.com"
    assert body["full_name"] == "" and body["first_name"] == ""
    assert body["avatar"] == {"kind": "initials", "preset_key": None, "version": 0, "urls": None}
    assert body["onboarding"] == {
        "status": "not_started",
        "mode": "full",
        "required_version": 3,
        "completed_version": 0,
        "next_step": "profile",
        "missing": ["profile", "course", "hours", "targets"],
    }
    assert body["course"] is None and body["last_visit"] is None
    assert Profile.objects.filter(pk=USER).exists() and Onboarding.objects.filter(pk=USER).exists()


def test_a_google_student_starts_with_the_provider_name_and_it_satisfies_the_name_step(make_token, db):
    from modules.profiles.tests.conftest import Api

    google = Api(make_token(user_metadata={"full_name": "Aarav Mehta", "picture": "https://img.example/a.png"}))
    body = google.get("/me/").json_body
    assert body["full_name"] == "Aarav Mehta" and body["first_name"] == "Aarav"
    assert body["onboarding"]["next_step"] == "course" and "profile" not in body["onboarding"]["missing"]
    assert Profile.objects.get(pk=USER).avatar_url == "https://img.example/a.png"  # not Google-hosted: never fetched


def test_an_unusable_provider_name_is_not_stored(make_token, db):
    from modules.profiles.tests.conftest import Api

    google = Api(make_token(user_metadata={"full_name": "bad\u202ename"}))
    body = google.get("/me/").json_body
    assert body["full_name"] == "" and body["onboarding"]["next_step"] == "profile"


def test_the_suggestion_comes_from_the_email_when_there_is_no_provider_name(api):
    assert api.get("/me/").json_body["name_suggestion"] == "Student"


def test_a_warm_bootstrap_costs_at_most_five_queries(api, scheme):
    api.get("/me/")  # first call creates the rows
    with CaptureQueriesContext(connection) as queries:
        assert api.get("/me/").status_code == 200
    assert len(queries) <= 5, [q["sql"][:80] for q in queries]


def test_etag_gives_304_when_nothing_changed(api):
    first = api.get("/me/")
    etag = first["ETag"]
    assert api.get("/me/", HTTP_IF_NONE_MATCH=etag).status_code == 304
    api.patch("/me/", {"full_name": "Aarav"})
    assert api.get("/me/", HTTP_IF_NONE_MATCH=etag).status_code == 200


def test_patch_saves_a_trimmed_normalised_name(api):
    res = api.patch("/me/", {"full_name": "  Aarav  Mehta "})
    assert res.status_code == 200
    assert res.json_body["full_name"] == "Aarav Mehta" and res.json_body["first_name"] == "Aarav"
    assert res.json_body["onboarding"]["missing"] == ["course", "hours", "targets"]


@pytest.mark.parametrize("bad", ["   ", "", "A" * 61, "x‮y"])
def test_patch_refuses_invalid_names_with_a_field_message(api, bad):
    res = api.patch("/me/", {"full_name": bad})
    assert res.status_code == 400
    assert "full_name" in res.json_body["error"]["details"]


def test_patch_requires_a_name(api):
    assert api.patch("/me/", {}).status_code == 400


@pytest.mark.parametrize("field", ["course", "level", "exam_date"])
def test_the_deprecated_course_fields_are_read_only(api, field):
    res = api.patch("/me/", {field: "ca"})
    assert res.status_code == 400 and res.json_body["error"]["code"] == "field_read_only"
    assert res.json_body["error"]["details"] == {"fields": [field]}


def test_patch_cannot_change_email_or_role(api):
    res = api.patch("/me/", {"full_name": "A", "email": "hacker@example.com", "role": "admin"})
    assert res.json_body["email"] == "student@example.com"
    assert Profile.objects.get(pk=USER).role == "student"


def test_each_student_only_ever_sees_their_own_profile(api, other_api):
    api.patch("/me/", {"full_name": "Aarav"})
    assert other_api.get("/me/").json_body["full_name"] == ""
    assert other_api.get("/me/").json_body["email"] == "other@example.com"


def test_a_long_legacy_name_is_left_alone_until_the_next_edit(api):
    api.get("/me/")
    Profile.objects.filter(pk=USER).update(full_name="L" * 100)
    assert api.get("/me/").json_body["full_name"] == "L" * 100
    assert api.patch("/me/", {"full_name": "L" * 100}).status_code == 400
