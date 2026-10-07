"""Small HTTP helpers shared by views."""

from __future__ import annotations

import hashlib
import hmac
import json

from rest_framework.response import Response


def tagged_response(request, payload: dict) -> Response:
    """
    200 with a weak ETag of the payload, or an empty 304 when the client already holds this exact version. The payload is
    built either way (the ETag is a hash of it), so this saves bandwidth and client re-renders, not server work.
    """
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True, default=str).encode(), usedforsecurity=False).hexdigest()
    etag = f'W/"{digest}"'
    if request.headers.get("If-None-Match") == etag:
        response = Response(status=304)
    else:
        response = Response(payload)
    response["ETag"] = etag
    return response


def service_role_headers(key: str) -> dict[str, str]:
    """
    Headers for Supabase REST calls made with the service-role key. A legacy key is a JWT and goes in both headers.
    The newer `sb_secret_...` keys are not JWTs: sent as a Bearer token they are rejected, so they go in `apikey` only.
    """
    headers = {"apikey": key}
    if key.count(".") == 2:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def request_has_secret(request, secret: str, header: str) -> bool:
    """
    True when the request carries `secret` in `header` or as `Authorization: Bearer <secret>` (what Vercel Cron sends).
    Constant-time comparison, and an unset secret never matches, so an unconfigured deploy refuses every caller.
    """
    if not secret:
        return False
    supplied = request.headers.get(header, "")
    if not supplied:
        auth = request.headers.get("Authorization", "")
        supplied = auth[len("Bearer ") :] if auth.startswith("Bearer ") else ""
    return hmac.compare_digest(supplied.encode(), secret.encode())
