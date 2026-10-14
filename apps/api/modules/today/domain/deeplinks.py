"""
The deep-link allow-list (PRD 11 Security, ERD 0.10). A task link is an internal `/app/...` path plus a flat object of scalar
values. Anything else (a scheme, a host, a query string inside the path, a path outside the list) is rejected, and the candidate
is dropped and counted as `invalid_link`. Pure: the route manifest test (W2) checks that every allowed prefix resolves on the web.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .constants import LINK_VALUE_MAX

#: The first two segments a provider may link into. Prefixes of modules that are not built yet (practice, mocks, ...) are listed
#: so their providers need no change here; the web route manifest test decides which of them must resolve today.
ALLOWED_PREFIXES: tuple[str, ...] = (
    "/app/syllabus",
    "/app/revision",
    "/app/recall",
    "/app/notes",
    "/app/focus",
    "/app/tracker",
    "/app/practice",
    "/app/questions",
    "/app/mocks",
    "/app/pyq",
    "/app/amendments",
    "/app/planner",
    "/app/today",
    "/app/settings",
)

#: Keys Today writes itself when it opens a link, so a provider may not set them.
RESERVED_SEARCH_KEYS = frozenset({"from", "task"})

_PATH = re.compile(r"^/app(?:/[A-Za-z0-9][A-Za-z0-9_.-]*)+$")
_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_MAX_SEARCH_KEYS = 8


def valid_path(path: str) -> bool:
    if not isinstance(path, str) or not _PATH.match(path) or ".." in path or len(path) > 200:
        return False
    return any(path == prefix or path.startswith(prefix + "/") for prefix in ALLOWED_PREFIXES)


def valid_search(search: Mapping[str, Any]) -> bool:
    if not isinstance(search, Mapping) or len(search) > _MAX_SEARCH_KEYS:
        return False
    for key, value in search.items():
        if not isinstance(key, str) or not _KEY.match(key) or key in RESERVED_SEARCH_KEYS:
            return False
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            return False
        if len(str(value)) > LINK_VALUE_MAX:
            return False
    return True


def valid_link(path: str, search: Mapping[str, Any]) -> bool:
    return valid_path(path) and valid_search(search)


def with_origin(search: Mapping[str, Any], task_id: str) -> dict[str, Any]:
    """The search object Today hands the browser: the provider's values plus `from=today&task=<id>` (FR-F13-23)."""
    return {**search, "from": "today", "task": task_id}
