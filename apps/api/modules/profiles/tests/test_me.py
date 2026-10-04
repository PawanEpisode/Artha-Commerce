import pytest

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


def test_me_creates_profile_lazily(auth_client):
    body = auth_client.get("/api/v1/me/").json()
    assert body["email"] == "student@example.com"
    assert body["course"] == ""


def test_me_patch_updates_allowed_fields(auth_client):
    res = auth_client.patch(
        "/api/v1/me/",
        data={"course": "ca", "level": "intermediate", "exam_date": "2027-05-02"},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.json()["course"] == "ca"


def test_me_patch_rejects_unknown_course(auth_client):
    res = auth_client.patch("/api/v1/me/", data={"course": "mba"}, content_type="application/json")
    assert res.status_code == 400
    assert "course" in res.json()["error"]["details"]


def test_me_patch_cannot_change_email(auth_client):
    res = auth_client.patch("/api/v1/me/", data={"email": "hacker@example.com"}, content_type="application/json")
    assert res.json()["email"] == "student@example.com"
