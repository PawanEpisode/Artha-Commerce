import uuid

import pytest

from core import storage
from modules.coverage.tests.conftest import OTHER, USER, Api, _fresh_throttle_counters  # noqa: F401


class FakeStorage:
    """In-memory object store with the surface of `core.storage.SupabaseStorage`."""

    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}
        self.fail_signing = False
        self.fail_delete = False
        self.buckets: set[str] = set()

    def upload(self, bucket, path, data, *, content_type, cache_control):
        self.objects[(bucket, path)] = data

    def delete(self, bucket, paths):
        if self.fail_delete:
            raise storage.StorageError("down")
        for p in paths:
            self.objects.pop((bucket, p), None)

    def list_prefix(self, bucket, prefix):
        return [p for (b, p) in self.objects if b == bucket and p.startswith(f"{prefix}/")]

    def public_url(self, bucket, path):
        return f"https://x.supabase.co/storage/v1/object/public/{bucket}/{path}"

    def create_signed_upload(self, bucket, path):
        if self.fail_signing:
            raise storage.StorageError("down")
        return storage.SignedUpload(f"https://x.supabase.co/storage/v1/object/upload/sign/{bucket}/{path}?token=t", "t")

    def create_signed_url(self, bucket, path, expires_in):
        return f"https://x.supabase.co/storage/v1/object/sign/{bucket}/{path}?token=r"

    def exists(self, bucket, path):
        return (bucket, path) in self.objects

    def read_range(self, bucket, path, start, end):
        if (bucket, path) not in self.objects:
            raise storage.StorageError("Storage answered 404")
        return self.objects[(bucket, path)][start : end + 1]

    def ensure_bucket(self, bucket, *, public=False):
        created = bucket not in self.buckets
        self.buckets.add(bucket)
        return created


@pytest.fixture
def fake_storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr("modules.media.services.get_storage", lambda: fake)
    return fake


@pytest.fixture
def api(make_token, db):
    return Api(make_token(sub=USER))


@pytest.fixture
def other_api(make_token, db):
    return Api(make_token(sub=OTHER))


def upload_image(c, fake, size=1000, mime="image/png", put=True):
    """The whole three-step flow; returns the attachment dict."""
    res = c.post("/media/uploads/", {"kind": "note_image", "mime": mime, "bytes": size})
    assert res.status_code == 201, res.json_body
    att = res.json_body["attachment"]
    if put:
        from modules.media.models import Attachment

        row = Attachment.objects.get(pk=att["id"])
        fake.upload(row.bucket, row.path, b"x" * size, content_type=mime, cache_control="")
    return att


def new_id():
    return str(uuid.uuid4())
