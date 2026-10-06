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
