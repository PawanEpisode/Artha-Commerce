import io

import pytest
from PIL import Image

from modules.profiles.models import Profile
from modules.profiles.services import provider_photo
from modules.profiles.tests.conftest import USER, Api

GOOGLE = "https://lh3.googleusercontent.com/a/abc123=s96-c"


def png(size=(300, 300)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (30, 90, 160)).save(out, "PNG")
    return out.getvalue()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (GOOGLE, "https://lh3.googleusercontent.com/a/abc123=s400-c"),
        ("https://lh3.googleusercontent.com/a/abc123", "https://lh3.googleusercontent.com/a/abc123"),
        ("http://lh3.googleusercontent.com/a/abc=s96-c", None),
        ("https://evil.example/a.png", None),
        ("https://googleusercontent.com.evil.example/a.png", None),
        ("https://user@lh3.googleusercontent.com/a.png", None),
        ("https://lh3.googleusercontent.com:8443/a.png", None),
        ("", None),
    ],
)
def test_only_google_image_urls_are_ever_fetched(raw, expected):
    assert provider_photo.photo_url(raw) == expected


@pytest.fixture
def google(make_token):
    return Api(make_token(user_metadata={"full_name": "Aarav Mehta", "picture": GOOGLE}))


def test_the_google_photo_becomes_the_first_avatar(google, fake_storage, monkeypatch, db):
    fetched = []
    monkeypatch.setattr(provider_photo, "fetch_photo", lambda url: fetched.append(url) or png())
    body = google.get("/me/").json_body
    assert fetched == ["https://lh3.googleusercontent.com/a/abc123=s400-c"]
    assert body["avatar"]["kind"] == "upload" and body["avatar"]["urls"]
    assert len(fake_storage.objects) == 2  # large and small renditions, our own files


def test_the_photo_is_imported_once_only(google, fake_storage, monkeypatch, db):
    calls = []
    monkeypatch.setattr(provider_photo, "fetch_photo", lambda url: calls.append(url) or png())
    google.get("/me/")
    google.delete("/me/avatar/")
    google.get("/me/")
    assert len(calls) == 1
    assert Profile.objects.get(pk=USER).avatar_kind == "initials"  # removing it sticks


@pytest.mark.parametrize(
    "failure", [lambda url: None, lambda url: b"not an image", lambda url: (_ for _ in ()).throw(OSError())]
)
def test_a_failed_import_leaves_initials_and_never_breaks_sign_in(google, fake_storage, monkeypatch, db, failure):
    monkeypatch.setattr(provider_photo, "fetch_photo", failure)
    res = google.get("/me/")
    assert res.status_code == 200 and res.json_body["avatar"]["kind"] == "initials"
    assert res.json_body["full_name"] == "Aarav Mehta"
    assert not fake_storage.objects


def test_a_storage_outage_leaves_initials(google, fake_storage, monkeypatch, db):
    fake_storage.fail_upload = True
    monkeypatch.setattr(provider_photo, "fetch_photo", lambda url: png())
    assert google.get("/me/").json_body["avatar"]["kind"] == "initials"


def test_nothing_is_fetched_when_the_avatar_flag_is_off(google, fake_storage, flag_off, monkeypatch, db):
    flag_off("profile_avatar")
    called = []
    monkeypatch.setattr(provider_photo, "fetch_photo", lambda url: called.append(url))
    assert google.get("/me/").json_body["avatar"]["kind"] == "initials"
    assert not called


def test_email_students_are_untouched(api, fake_storage, monkeypatch, db):
    monkeypatch.setattr(provider_photo, "fetch_photo", lambda url: pytest.fail("no photo to fetch"))
    assert api.get("/me/").json_body["avatar"]["kind"] == "initials"
