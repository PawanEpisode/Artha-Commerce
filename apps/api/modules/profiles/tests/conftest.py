import json
import time
from collections.abc import Iterator

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from core import auth_admin, feature_flags, storage
from modules.syllabus.models import ExamTerm
from modules.syllabus.tests.helpers import make_scheme

USER = "3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11"
OTHER = "9a1e7c52-1a5b-4d6e-8c3f-2b7d4e5f6a70"


class Api:
    """Tiny JSON client bound to one student."""

    def __init__(self, token: str):
        self.c = Client(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _send(self, method, path, body=None, **headers):
        res = getattr(self.c, method)(
            f"/api/v1{path}",
            data=json.dumps(body) if body is not None else None,
            content_type="application/json",
            **headers,
        )
        res.json_body = res.json() if res.content else None
        return res

    def get(self, path, **headers):
        return self._send("get", path, **headers)

    def post(self, path, body=None):
        return self._send("post", path, body or {})

    def put(self, path, body=None):
        return self._send("put", path, body or {})

    def patch(self, path, body=None):
        return self._send("patch", path, body or {})

    def delete(self, path, body=None):
        return self._send("delete", path, body)

    def upload(self, path, data: bytes, *, name="photo.jpg", content_type="image/jpeg"):
        res = self.c.post(f"/api/v1{path}", data={"file": SimpleUploadedFile(name, data, content_type=content_type)})
        res.json_body = res.json() if res.content else None
        return res


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api(make_token, db):
    return Api(make_token(sub=USER))


@pytest.fixture
def other_api(make_token, db):
    return Api(make_token(sub=OTHER, email="other@example.com"))


@pytest.fixture
def scheme(db):
    return make_scheme()


@pytest.fixture
def ids(scheme):
    return {
        "scheme": str(scheme.id),
        "term": str(ExamTerm.objects.get(level__course__code="ca", level__code="intermediate", code="2027-05").id),
    }


class FakeStorage:
    """In-memory object store with the same surface as `core.storage.SupabaseStorage`."""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.fail_delete = False
        self.fail_upload = False
        self.fail_upload_after: int | None = None  # fail every upload once this many have stored
        self.last_upload: dict = {}

    def upload(self, bucket, path, data, *, content_type, cache_control):
        if self.fail_upload or (self.fail_upload_after is not None and len(self.objects) >= self.fail_upload_after):
            raise storage.StorageError("down")
        self.objects[(bucket, path)] = data
        self.last_upload = {"content_type": content_type, "cache_control": cache_control}

    def delete(self, bucket, paths):
        if self.fail_delete:
            raise storage.StorageError("down")
        for path in paths:
            self.objects.pop((bucket, path), None)

    def list_prefix(self, bucket, prefix):
        return [p for (b, p) in self.objects if b == bucket and p.startswith(f"{prefix}/")]

    def public_url(self, bucket, path):
        return f"https://x.supabase.co/storage/v1/object/public/{bucket}/{path}"


@pytest.fixture
def fake_storage(monkeypatch) -> Iterator[FakeStorage]:
    fake = FakeStorage()
    monkeypatch.setattr(storage, "get_storage", lambda: fake)
    monkeypatch.setattr("modules.profiles.services.account.get_storage", lambda: fake)
    yield fake


@pytest.fixture
def deleted_auth_users(monkeypatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr(auth_admin, "delete_user", lambda user_id: calls.append(user_id))
    return calls


@pytest.fixture
def fresh_login(make_token):
    """A token whose `amr` proves a sign-in a minute ago (the reauthentication window is 10 minutes)."""

    def _make(sub=USER):
        return Api(make_token(sub=sub, amr=[{"method": "otp", "timestamp": int(time.time()) - 60}]))

    return _make


@pytest.fixture
def flag_off(settings, monkeypatch):
    """`flag_off("name")` turns one PostHog flag off for the test (flags fail open otherwise)."""

    def make(name):
        class Off:
            def get_feature_flag(self, key, distinct_id, **kwargs):
                return False if key == name else None

        settings.POSTHOG_API_KEY = "phc_test"
        monkeypatch.setattr(feature_flags, "_client", Off())
        feature_flags.clear_flag_cache()

    yield make
    feature_flags.clear_flag_cache()
