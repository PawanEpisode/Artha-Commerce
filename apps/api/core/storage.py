"""
Supabase Storage over REST with the service-role key (PRD F-16 ERD section 6). Server side only: the browser never
holds a Storage credential and never uploads directly. One small client so every module (avatars now, media in F-06)
shares the same timeouts, headers and error handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import httpx
from django.conf import settings

from .http import service_role_headers

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=3.0)


class StorageError(Exception):
    """The object store refused or could not be reached. Callers queue a retry instead of failing the user."""


@dataclass(frozen=True)
class SignedUpload:
    """Where the browser sends the bytes: `PUT url` with the file as the body. Valid for a short time, one object."""

    url: str
    token: str


class Storage(Protocol):
    def upload(self, bucket: str, path: str, data: bytes, *, content_type: str, cache_control: str) -> None: ...

    def delete(self, bucket: str, paths: list[str]) -> None: ...

    def list_prefix(self, bucket: str, prefix: str) -> list[str]: ...

    def public_url(self, bucket: str, path: str) -> str: ...

    def create_signed_upload(self, bucket: str, path: str) -> SignedUpload: ...

    def create_signed_url(self, bucket: str, path: str, expires_in: int) -> str: ...

    def exists(self, bucket: str, path: str) -> bool: ...

    def ensure_bucket(self, bucket: str, *, public: bool = False) -> bool: ...


class SupabaseStorage:
    def __init__(self, base_url: str, service_key: str):
        self._base = f"{base_url.rstrip('/')}/storage/v1"
        self._headers = service_role_headers(service_key)

    def _request(
        self, method: str, url: str, *, headers: dict[str, str] | None = None, allow: tuple[int, ...] = (), **kwargs
    ) -> httpx.Response:
        try:
            response = httpx.request(
                method, url, headers={**self._headers, **(headers or {})}, timeout=TIMEOUT, **kwargs
            )
        except httpx.HTTPError as exc:
            raise StorageError(f"Storage unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400 and response.status_code not in allow:
            raise StorageError(f"Storage answered {response.status_code}")
        return response

    def upload(self, bucket: str, path: str, data: bytes, *, content_type: str, cache_control: str) -> None:
        self._request(
            "POST",
            f"{self._base}/object/{bucket}/{path}",
            content=data,
            headers={
                "content-type": content_type,
                "cache-control": cache_control,
                "x-upsert": "false",
            },
        )

    def delete(self, bucket: str, paths: list[str]) -> None:
        if paths:
            self._request("DELETE", f"{self._base}/object/{bucket}", json={"prefixes": paths})

    def list_prefix(self, bucket: str, prefix: str) -> list[str]:
        """Object paths directly under `prefix/` (avatars keep at most two live objects per student)."""
        response = self._request(
            "POST", f"{self._base}/object/list/{bucket}", json={"prefix": prefix, "limit": 100, "offset": 0}
        )
        return [f"{prefix}/{item['name']}" for item in response.json() if item.get("name")]

    def public_url(self, bucket: str, path: str) -> str:
        return f"{self._base}/object/public/{bucket}/{path}"

    def create_signed_upload(self, bucket: str, path: str) -> SignedUpload:
        """A one-object upload URL, so private files go from the browser straight to storage and never through Vercel."""
        body = self._request("POST", f"{self._base}/object/upload/sign/{bucket}/{path}").json()
        return SignedUpload(url=f"{self._base}{body['url']}", token=body.get("token", ""))

    def create_signed_url(self, bucket: str, path: str, expires_in: int) -> str:
        """A time-limited read URL for a private object. Callers check ownership first; the URL itself is a capability."""
        body = self._request(
            "POST", f"{self._base}/object/sign/{bucket}/{path}", json={"expiresIn": int(expires_in)}
        ).json()
        return f"{self._base}{body['signedURL']}"

    def exists(self, bucket: str, path: str) -> bool:
        return self._request("GET", f"{self._base}/object/info/{bucket}/{path}", allow=(404,)).status_code == 200

    def ensure_bucket(self, bucket: str, *, public: bool = False) -> bool:
        """Creates the bucket when it is missing. True when it was created, False when it already existed."""
        response = self._request(
            "POST", f"{self._base}/bucket", json={"id": bucket, "name": bucket, "public": public}, allow=(400, 409)
        )
        return response.status_code < 400


def get_storage() -> Storage:
    """Tests replace this with an in-memory fake. Missing configuration is a loud error, never a silent skip."""
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise StorageError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
    return SupabaseStorage(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def public_url(bucket: str, path: str) -> str:
    """Public object URL without needing the service key (reads go through the CDN)."""
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
