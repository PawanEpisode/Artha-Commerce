"""Supabase Auth Admin API (service role): the one call we need, deleting a user at account deletion."""

from __future__ import annotations

import httpx
from django.conf import settings

from .http import service_role_headers
from .storage import TIMEOUT


class AuthAdminError(Exception):
    pass


def delete_user(user_id: str) -> None:
    """Idempotent: a user that is already gone (404) counts as deleted so a retried account deletion can finish."""
    if not settings.SUPABASE_SERVICE_ROLE_KEY:
        raise AuthAdminError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    try:
        response = httpx.delete(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}",
            headers=service_role_headers(key),
            timeout=TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise AuthAdminError(f"Auth unreachable: {type(exc).__name__}") from exc
    if response.status_code not in (200, 204, 404):
        raise AuthAdminError(f"Auth answered {response.status_code}")
