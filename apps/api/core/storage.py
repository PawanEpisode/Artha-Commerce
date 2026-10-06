"""
Supabase Storage over REST with the service-role key (PRD F-16 ERD section 6). Server side only: the browser never
holds a Storage credential and never uploads directly. One small client so every module (avatars now, media in F-06)
shares the same timeouts, headers and error handling.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx
from django.conf import settings

from .http import service_role_headers

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(10.0, connect=3.0)


class StorageError(Exception):
    """The object store refused or could not be reached. Callers queue a retry instead of failing the user."""


class Storage(Protocol):
    def upload(self, bucket: str, path: str, data: bytes, *, content_type: str, cache_control: str) -> None: ...

    def delete(self, bucket: str, paths: list[str]) -> None: ...

    def list_prefix(self, bucket: str, prefix: str) -> list[str]: ...

    def public_url(self, bucket: str, path: str) -> str: ...


class SupabaseStorage:
    def __init__(self, base_url: str, service_key: str):
        self._base = f"{base_url.rstrip('/')}/storage/v1"
        self._headers = service_role_headers(service_key)

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        try:
            response = httpx.request(method, url, headers=self._headers, timeout=TIMEOUT, **kwargs)
        except httpx.HTTPError as exc:
            raise StorageError(f"Storage unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise StorageError(f"Storage answered {response.status_code}")
        return response

    def upload(self, bucket: str, path: str, data: bytes, *, content_type: str, cache_control: str) -> None:
        self._request(
            "POST",
            f"{self._base}/object/{bucket}/{path}",
            content=data,
            headers={
                **self._headers,
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


def get_storage() -> Storage:
    """Tests replace this with an in-memory fake. Missing configuration is a loud error, never a silent skip."""
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise StorageError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
    return SupabaseStorage(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def public_url(bucket: str, path: str) -> str:
    """Public object URL without needing the service key (reads go through the CDN)."""
    return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
