"""
Which pages are worth coming back to, and which query keys survive (PRD section 7). Pure; the web mirrors it in
`personalization/lib/restorable.ts` and both are tested against `tests/fixtures/restorable_cases.json`.

Rules: pathname only, one of the listed routes, segments are plain slugs or ids, no `..`, no `//`, no encoding, no
control characters. Of the query string only the keys a route lists survive, with simple values: dates are dropped on
purpose (a stale date is not useful), so are tokens and tracking parameters.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlencode

MAX_PATH = 300
MAX_SEARCH = 200

_SEGMENT = r"[A-Za-z0-9_-]{1,64}"
_VALUE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

#: (path pattern, query keys that survive). Not listed means not restorable: onboarding, account, settings, day pages.
RESTORABLE_ROUTES: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = tuple(
    (re.compile(pattern), frozenset(keys))
    for pattern, keys in (
        (r"^/app$", ()),
        (r"^/app/syllabus$", ("view", "status")),
        (rf"^/app/syllabus/{_SEGMENT}$", ()),
        (rf"^/app/syllabus/{_SEGMENT}/{_SEGMENT}$", ()),
        (r"^/app/revision$", ()),
        (r"^/app/tracker$", ()),
        (r"^/app/tracker/reports$", ("range", "by")),
        (r"^/app/tracker/log$", ()),
        (r"^/app/tracker/goals$", ()),
        (r"^/app/focus$", ()),
        (r"^/app/focus/history$", ()),
    )
)


def _clean_path(path: str) -> str | None:
    if not path or len(path) > MAX_PATH or not path.startswith("/"):
        return None
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path


def clean_visit(path: str, search: str = "") -> tuple[str, str] | None:
    """The `(path, search)` to store, or None when the page is not restorable."""
    cleaned = _clean_path(path)
    if cleaned is None:
        return None
    for pattern, keys in RESTORABLE_ROUTES:
        if pattern.fullmatch(cleaned):  # fullmatch: `$` would accept a trailing newline
            return cleaned, _clean_search(search, keys)
    return None


def _clean_search(search: str, keys: frozenset[str]) -> str:
    if not keys or not search or len(search) > MAX_SEARCH:
        return ""
    kept = [(k, v) for k, v in parse_qsl(search.lstrip("?"), keep_blank_values=False) if k in keys and _VALUE.match(v)]
    return urlencode(kept)
