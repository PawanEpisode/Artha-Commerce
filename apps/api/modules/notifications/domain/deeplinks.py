"""
A notification may only open a page inside the student's own workspace. Links are relative paths checked against an
allow-list when the notification is created, and again by the service worker before it opens one.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

EXACT_ROUTES = frozenset({"/app"})
ALLOWED_PREFIXES = (
    "/app/focus",
    "/app/tracker",
    "/app/revision",
    "/app/syllabus",
    "/app/notifications",
    "/app/settings/notifications",
)
MAX_LENGTH = 200  # matches the database column

_ENCODED_TRICKS = re.compile(r"%2e|%2f|%5c", re.IGNORECASE)


class InvalidDeepLink(ValueError):
    """The path is not a relative link to an allowed page."""


def validate_deep_link(path: str) -> str:
    """Returns `path` unchanged when it is allowed; raises `InvalidDeepLink` otherwise."""
    if not isinstance(path, str) or not path or len(path) > MAX_LENGTH:
        raise InvalidDeepLink("A deep link must be a non-empty string of at most 200 characters.")
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise InvalidDeepLink("A deep link must be a relative path that starts with a single slash.")
    if any(ord(char) < 32 or ord(char) == 127 for char in path) or _ENCODED_TRICKS.search(path):
        raise InvalidDeepLink("A deep link may not contain control characters or encoded slashes or dots.")
    parts = urlsplit(path)
    if parts.scheme or parts.netloc:
        raise InvalidDeepLink("A deep link may not name another site.")
    segments = parts.path.split("/")
    if any(segment in {".", ".."} for segment in segments):
        raise InvalidDeepLink("A deep link may not climb out of its folder.")
    route = parts.path.rstrip("/") or "/"
    if route in EXACT_ROUTES or any(route == prefix or route.startswith(prefix + "/") for prefix in ALLOWED_PREFIXES):
        return path
    raise InvalidDeepLink("That page is not on the notification allow-list.")


def is_allowed(path: str) -> bool:
    try:
        validate_deep_link(path)
    except InvalidDeepLink:
        return False
    return True
