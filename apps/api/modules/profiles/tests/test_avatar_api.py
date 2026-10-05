"""Avatar endpoints: preset, upload, replace, remove, failures and the retry queue."""

import io

import pytest
from django.core.management import call_command
from PIL import Image

from core import storage
from modules.profiles.domain import avatars
from modules.profiles.models import Profile, StorageDelete
from modules.profiles.tests.conftest import USER

pytestmark = pytest.mark.django_db

BUCKET = "avatars"


def jpeg(size=(600, 600)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(out, format="JPEG")
    return out.getvalue()


def profile() -> Profile:
    return Profile.objects.get(pk=USER)


def object_names(fake):
    return sorted(path for _, path in fake.objects)


# --- preset ---------------------------------------------------------------------------------------


def test_a_new_student_has_initials_and_version_zero(api):
    avatar = api.get("/me/").json_body["avatar"]
    assert avatar == {"kind": "initials", "preset_key": None, "version": 0, "urls": None}


def test_choosing_a_preset_stores_only_the_key(api, fake_storage):
    res = api.put("/me/avatar/preset/", {"key": "p07"})
    assert res.status_code == 200
    assert res.json_body == {"kind": "preset", "preset_key": "p07", "version": 1, "urls": None}
    assert profile().avatar_key == "" and fake_storage.objects == {}
    assert api.get("/me/").json_body["avatar"]["preset_key"] == "p07"


@pytest.mark.parametrize("key", ["p00", "p25", "P01", "", "../x", "p1"])
def test_an_unknown_preset_is_refused(api, key):
    res = api.put("/me/avatar/preset/", {"key": key})
    assert res.status_code == 400 and res.json_body["error"]["code"] in {"unknown_preset", "invalid"}
    assert profile().avatar_kind == "initials" if Profile.objects.filter(pk=USER).exists() else True


def test_every_catalogue_key_is_accepted(api):
    for key in avatars.PRESET_KEYS:
        assert api.put("/me/avatar/preset/", {"key": key}).status_code == 200


def test_a_preset_replaces_an_uploaded_photo_and_deletes_its_files(api, fake_storage):
    assert api.upload("/me/avatar/", jpeg()).status_code == 201
    assert len(fake_storage.objects) == 2
    assert api.put("/me/avatar/preset/", {"key": "p02"}).status_code == 200
    assert fake_storage.objects == {}


# --- upload ---------------------------------------------------------------------------------------


def test_upload_stores_two_renditions_under_the_students_prefix(api, fake_storage):
    res = api.upload("/me/avatar/", jpeg())
    assert res.status_code == 201
    body = res.json_body
    assert body["kind"] == "upload" and body["version"] == 1 and body["preset_key"] is None
    names = object_names(fake_storage)
    assert len(names) == 2 and all(n.startswith(f"{USER}/") for n in names)
    assert {n.rsplit("-", 1)[1] for n in names} == {"512.webp", "128.webp"}
    assert body["urls"]["large"].endswith(names[1] if names[1].endswith("512.webp") else names[0])
    assert "128.webp" in body["urls"]["small"]


def test_the_stored_files_are_webp_with_long_cache_headers(api, fake_storage):
    api.upload("/me/avatar/", jpeg())
    for blob in fake_storage.objects.values():
        assert blob[:4] == b"RIFF" and blob[8:12] == b"WEBP"
    assert fake_storage.last_upload["cache_control"] == "public, max-age=31536000, immutable"
    assert fake_storage.last_upload["content_type"] == "image/webp"


def test_replacing_a_photo_uses_a_new_url_and_deletes_the_old_pair(api, fake_storage):
    first = api.upload("/me/avatar/", jpeg()).json_body
    old = set(fake_storage.objects)
    second = api.upload("/me/avatar/", jpeg()).json_body
    assert second["version"] == 2
    assert second["urls"]["large"] != first["urls"]["large"]
    assert len(fake_storage.objects) == 2 and not (old & set(fake_storage.objects))


def test_removing_the_photo_deletes_both_files_and_goes_back_to_initials(api, fake_storage):
    api.upload("/me/avatar/", jpeg())
    res = api.delete("/me/avatar/")
    assert res.status_code == 200 and res.json_body["kind"] == "initials" and res.json_body["urls"] is None
    assert res.json_body["version"] == 2
    assert fake_storage.objects == {} and profile().avatar_key == ""


def test_removing_with_nothing_to_remove_is_fine(api, fake_storage):
    assert api.delete("/me/avatar/").status_code == 200


# --- upload: refusals -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "name", "ctype", "code"),
    [
        (b"not an image", "a.jpg", "image/jpeg", "invalid_image"),
        (b'<svg xmlns="http://www.w3.org/2000/svg"/>', "a.svg", "image/svg+xml", "invalid_image"),
    ],
)
def test_bad_files_are_400_with_a_code(api, fake_storage, data, name, ctype, code):
    res = api.upload("/me/avatar/", data, name=name, content_type=ctype)
    assert res.status_code == 400 and res.json_body["error"]["code"] == code
    assert fake_storage.objects == {}


def test_a_small_photo_is_refused(api, fake_storage):
    res = api.upload("/me/avatar/", jpeg((100, 100)))
    assert res.status_code == 400 and res.json_body["error"]["code"] == "image_too_small"


def test_a_missing_file_is_invalid(api, fake_storage):
    res = api.post("/me/avatar/")  # JSON body, not multipart
    assert res.status_code in (400, 415)


def test_an_oversized_upload_is_413_and_nothing_is_stored(api, fake_storage):
    res = api.upload("/me/avatar/", b"\xff\xd8" + b"0" * 1_100_000)
    assert res.status_code == 413 and res.json_body["error"]["code"] == "payload_too_large"
    assert fake_storage.objects == {}


def test_with_the_flag_off_upload_is_403_but_presets_and_remove_still_work(api, flag_off, fake_storage):
    flag_off("profile_avatar")
    res = api.upload("/me/avatar/", jpeg())
    assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"
    assert api.put("/me/avatar/preset/", {"key": "p01"}).status_code == 200
    assert api.delete("/me/avatar/").status_code == 200


def test_endpoints_need_a_signed_in_student(client):
    for method, path in (("post", "/api/v1/me/avatar/"), ("delete", "/api/v1/me/avatar/")):
        assert getattr(client, method)(path).status_code == 401
    assert client.put("/api/v1/me/avatar/preset/", {"key": "p01"}, content_type="application/json").status_code == 401


def test_uploads_are_throttled(api, fake_storage):
    codes = [api.upload("/me/avatar/", jpeg((200, 200))).status_code for _ in range(11)]
    assert codes[:10] == [201] * 10 and codes[10] == 429


# --- failures -------------------------------------------------------------------------------------


def test_a_storage_outage_is_503_and_the_old_avatar_stays(api, fake_storage):
    api.put("/me/avatar/preset/", {"key": "p05"})
    fake_storage.fail_upload = True
    res = api.upload("/me/avatar/", jpeg())
    assert res.status_code == 503 and res.json_body["error"]["code"] == "storage_unavailable"
    assert profile().avatar_kind == "preset" and profile().avatar_preset_key == "p05"
    assert fake_storage.objects == {}


def test_a_failure_after_the_first_object_removes_what_was_stored(api, fake_storage):
    api.put("/me/avatar/preset/", {"key": "p05"})
    fake_storage.fail_upload_after = 1  # the 512 stores, the 128 fails
    res = api.upload("/me/avatar/", jpeg())
    assert res.status_code == 503
    assert fake_storage.objects == {} and profile().avatar_kind == "preset"


def test_a_failed_delete_of_the_old_pair_does_not_fail_the_request_and_is_queued(api, fake_storage):
    api.upload("/me/avatar/", jpeg())
    old = object_names(fake_storage)
    fake_storage.fail_delete = True
    res = api.upload("/me/avatar/", jpeg())
    assert res.status_code == 201
    assert sorted(StorageDelete.objects.values_list("path", flat=True)) == old


def test_the_sweep_retries_queued_deletes_and_clears_the_rows(api, fake_storage):
    api.upload("/me/avatar/", jpeg())
    fake_storage.fail_delete = True
    api.delete("/me/avatar/")
    assert StorageDelete.objects.count() == 2 and len(fake_storage.objects) == 2

    fake_storage.fail_delete = False
    call_command("sweep_avatars")
    assert StorageDelete.objects.count() == 0 and fake_storage.objects == {}


def test_the_sweep_keeps_failing_rows_and_counts_attempts(api, fake_storage):
    api.upload("/me/avatar/", jpeg())
    fake_storage.fail_delete = True
    api.delete("/me/avatar/")
    call_command("sweep_avatars")
    assert set(StorageDelete.objects.values_list("attempts", flat=True)) == {1}


def test_a_missing_service_key_is_a_clean_503_not_a_crash(api, settings, monkeypatch):
    settings.SUPABASE_SERVICE_ROLE_KEY = ""
    monkeypatch.undo()  # use the real get_storage
    res = api.upload("/me/avatar/", jpeg())
    assert res.status_code == 503 and storage.StorageError is not None
