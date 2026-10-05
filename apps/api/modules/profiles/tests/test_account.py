"""Account export and deletion: confirmation, reauthentication, ordering, partial failure and retry."""

import pytest

from core import events, registry
from modules.coverage.models import Enrollment
from modules.profiles.models import Onboarding, Profile
from modules.profiles.tests.conftest import OTHER, USER

pytestmark = pytest.mark.django_db

BUCKET = "avatars"


def enroll(api, ids):
    assert (
        api.put("/me/onboarding/steps/course/", {"scheme": ids["scheme"], "target_term": ids["term"]}).status_code
        == 200
    )


# --- registry ---------------------------------------------------------------------------------


def test_every_module_holding_student_data_registers_an_eraser_and_an_exporter():
    erasers = {name for name, _ in registry.erasers()}
    exporters = {name for name, _ in registry.exporters()}
    assert {"coverage", "tracking", "focus"} <= erasers
    assert erasers == exporters


# --- export -----------------------------------------------------------------------------------


def test_export_contains_the_profile_and_every_module(api, ids):
    api.get("/me/")
    enroll(api, ids)
    res = api.get("/me/export/")
    assert res.status_code == 200
    body = res.json_body
    assert body["profile"]["email"]
    assert {"coverage", "tracking", "focus"} <= set(body["modules"])
    assert body["modules"]["coverage"]["enrollments"]


def test_export_of_a_fresh_account_is_empty_but_well_formed(api):
    body = api.get("/me/export/").json_body
    assert body["onboarding"] is None and body["last_visit"] is None


def test_export_never_includes_another_students_data(api, other_api, ids):
    enroll(other_api, ids)
    body = api.get("/me/export/").json_body
    assert body["modules"]["coverage"]["enrollments"] == []


# --- delete: guards ---------------------------------------------------------------------------


def test_delete_needs_the_typed_word(fresh_login, fake_storage, deleted_auth_users):
    api = fresh_login()
    api.get("/me/")
    for body in ({}, {"confirm": "delete"}, {"confirm": "yes"}):
        res = api.delete("/me/", body)
        assert res.status_code == 400 and res.json_body["error"]["code"] == "confirmation_required"
    assert Profile.objects.filter(pk=USER).exists() and deleted_auth_users == []


def test_delete_needs_a_recent_authentication(api, fake_storage, deleted_auth_users):
    api.get("/me/")
    res = api.delete("/me/", {"confirm": "DELETE"})
    assert res.status_code == 401 and res.json_body["error"]["code"] == "reauth_required"
    assert Profile.objects.filter(pk=USER).exists() and deleted_auth_users == []


# --- delete: happy path -----------------------------------------------------------------------


def test_delete_removes_everything_and_the_auth_user(fresh_login, ids, fake_storage, deleted_auth_users):
    api = fresh_login()
    api.get("/me/")
    enroll(api, ids)
    fake_storage.objects[(BUCKET, f"{USER}/a.webp")] = b"x"
    fake_storage.objects[(BUCKET, f"{OTHER}/keep.webp")] = b"y"
    seen = []
    events.subscribe("account_deleted", lambda **payload: seen.append(payload))

    res = api.delete("/me/", {"confirm": "DELETE"})

    assert res.status_code == 204
    assert not Profile.objects.filter(pk=USER).exists()
    assert not Onboarding.objects.filter(pk=USER).exists()
    assert not Enrollment.objects.filter(user_id=USER).exists()
    assert list(fake_storage.objects) == [(BUCKET, f"{OTHER}/keep.webp")]
    assert deleted_auth_users == [USER]
    assert len(seen) == 1 and USER not in str(seen[0])


def test_delete_leaves_other_students_untouched(fresh_login, other_api, ids, fake_storage, deleted_auth_users):
    other_api.get("/me/")
    enroll(other_api, ids)
    api = fresh_login()
    api.get("/me/")
    assert api.delete("/me/", {"confirm": "DELETE"}).status_code == 204
    assert Profile.objects.filter(pk=OTHER).exists()
    assert Enrollment.objects.filter(user_id=OTHER).exists()


# --- delete: partial failure and retry --------------------------------------------------------


def test_a_storage_failure_is_reported_and_a_retry_finishes_the_job(fresh_login, ids, fake_storage, deleted_auth_users):
    api = fresh_login()
    api.get("/me/")
    enroll(api, ids)
    fake_storage.objects[(BUCKET, f"{USER}/a.webp")] = b"x"
    fake_storage.fail_delete = True

    res = api.delete("/me/", {"confirm": "DELETE"})

    assert res.status_code == 500 and res.json_body["error"]["code"] == "deletion_incomplete"
    details = res.json_body["error"]["details"]
    assert details["failed"] == "avatar_files" and "coverage" in details["done"]
    assert Profile.objects.filter(pk=USER).exists() and deleted_auth_users == []

    fake_storage.fail_delete = False
    assert api.delete("/me/", {"confirm": "DELETE"}).status_code == 204
    assert not Profile.objects.filter(pk=USER).exists()
    assert deleted_auth_users == [USER]
    assert not fake_storage.objects


def test_an_auth_failure_after_the_data_is_gone_can_be_retried(fresh_login, fake_storage, monkeypatch):
    from core import auth_admin

    api = fresh_login()
    api.get("/me/")
    calls = {"n": 0}

    def flaky(user_id):
        calls["n"] += 1
        if calls["n"] == 1:
            raise auth_admin.AuthAdminError("down")

    monkeypatch.setattr(auth_admin, "delete_user", flaky)

    first = api.delete("/me/", {"confirm": "DELETE"})
    assert first.status_code == 500 and first.json_body["error"]["details"]["failed"] == "auth"
    assert api.delete("/me/", {"confirm": "DELETE"}).status_code == 204
    assert calls["n"] == 2
