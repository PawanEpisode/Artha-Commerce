import httpx
import pytest

from core.storage import StorageError, SupabaseStorage


class Calls(list):
    status = 200


@pytest.fixture
def calls(monkeypatch):
    seen = Calls()

    def fake(method, url, **kwargs):
        seen.append((method, url, kwargs))
        return httpx.Response(seen.status, json=[{"name": "a.webp"}], request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake)
    return seen


def test_upload_sends_object_headers_merged_with_the_credentials(calls):
    SupabaseStorage("https://x.supabase.co", "sb_secret_abc").upload(
        "avatars", "u/k.webp", b"data", content_type="image/webp", cache_control="public, max-age=1"
    )
    method, url, kwargs = calls[0]
    assert (method, url) == ("POST", "https://x.supabase.co/storage/v1/object/avatars/u/k.webp")
    assert kwargs["headers"]["apikey"] == "sb_secret_abc"
    assert kwargs["headers"]["content-type"] == "image/webp"
    assert kwargs["headers"]["cache-control"] == "public, max-age=1"
    assert kwargs["headers"]["x-upsert"] == "false"
    assert "Authorization" not in kwargs["headers"]


def test_list_and_delete_use_the_credentials(calls):
    store = SupabaseStorage("https://x.supabase.co", "a.b.c")
    assert store.list_prefix("avatars", "u") == ["u/a.webp"]
    store.delete("avatars", ["u/a.webp"])
    assert calls[0][2]["headers"]["Authorization"] == "Bearer a.b.c"


def test_a_refusal_becomes_a_storage_error(calls):
    calls.status = 404
    with pytest.raises(StorageError, match="404"):
        SupabaseStorage("https://x.supabase.co", "k").delete("avatars", ["p"])


def test_signed_upload_and_read_urls_are_absolute_storage_urls(monkeypatch):
    def fake(method, url, **kwargs):
        body = {"url": "/object/upload/sign/b/p?token=t", "token": "t"} if "upload/sign" in url else None
        body = body or {"signedURL": "/object/sign/b/p?token=r"}
        return httpx.Response(200, json=body, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake)
    store = SupabaseStorage("https://x.supabase.co", "k")
    up = store.create_signed_upload("b", "p")
    assert (up.url, up.token) == ("https://x.supabase.co/storage/v1/object/upload/sign/b/p?token=t", "t")
    assert store.create_signed_url("b", "p", 3600) == "https://x.supabase.co/storage/v1/object/sign/b/p?token=r"


def test_exists_is_false_on_404_and_errors_on_other_failures(calls):
    store = SupabaseStorage("https://x.supabase.co", "k")
    assert store.exists("b", "p") is True
    calls.status = 404
    assert store.exists("b", "p") is False
    calls.status = 500
    with pytest.raises(StorageError):
        store.exists("b", "p")
