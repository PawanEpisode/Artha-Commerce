"""
Uses the sign-in provider's photo as the first avatar (best effort, once, at the first sign-in). The photo is fetched by
the server from Google's image host only, re-encoded through the normal upload pipeline and stored as our own file:
never hotlinked, so the student's browser never talks to Google for it and the photo does not vanish when they change
it there. Any failure just leaves initials; the student can upload or pick an avatar at any time.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urlsplit

import httpx

from ..domain.images import MAX_INPUT_BYTES
from .avatar import set_upload

logger = logging.getLogger(__name__)

TIMEOUT = httpx.Timeout(3.0, connect=2.0)
ALLOWED_HOST_SUFFIX = ".googleusercontent.com"
#: Google serves `...=s96-c` (a 96 px crop). Ask for a size that survives the 256 px large rendition.
_SIZE = re.compile(r"=s\d+(-c)?$")
WANTED_SIZE = "=s400-c"


def photo_url(raw: str) -> str | None:
    """The URL to fetch, or None when it is not an https Google image URL (so nothing else is ever requested)."""
    try:
        parts = urlsplit(raw or "")
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if (
        parts.scheme != "https"
        or parts.port not in (None, 443)
        or parts.username
        or not host.endswith(ALLOWED_HOST_SUFFIX)
    ):
        return None
    return _SIZE.sub(WANTED_SIZE, raw) if _SIZE.search(raw) else raw


def fetch_photo(url: str) -> bytes | None:
    """No redirects, short timeouts, image content types only, and never more than the upload limit."""
    with httpx.stream("GET", url, timeout=TIMEOUT, follow_redirects=False) as response:
        if response.status_code != 200 or not response.headers.get("content-type", "").startswith("image/"):
            return None
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > MAX_INPUT_BYTES:
                return None
        return bytes(data)


def import_provider_photo(user_id, raw_url: str) -> bool:
    """True when the photo became the student's avatar. Never raises."""
    url = photo_url(raw_url)
    if url is None:
        return False
    try:
        data = fetch_photo(url)
        if not data:
            return False
        set_upload(user_id, data)
    except Exception as exc:  # a missing photo must never break the first sign-in
        logger.info("provider photo not imported: %s", type(exc).__name__)
        return False
    return True
