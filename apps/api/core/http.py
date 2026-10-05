"""Small HTTP helpers shared by views."""

from __future__ import annotations

import hashlib
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
