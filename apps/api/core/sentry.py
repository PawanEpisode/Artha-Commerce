"""Sentry hooks. Bodies of endpoints that carry a token or behavioural data never leave the API."""

from typing import Any

#: Paths whose request body is dropped from every event (the beacon body holds an access token; a notification button
#: carries its one-time token).
SCRUBBED_BODY_PATHS = ("/me/last-visit/", "/notifications/actions/")
#: Keys whose values are replaced wherever they appear in request data or local variables.
SCRUBBED_KEYS = frozenset({"token"})
FILTERED = "[Filtered]"


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return value
    if isinstance(value, dict):
        return {k: FILTERED if str(k).lower() in SCRUBBED_KEYS else _scrub(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v, depth + 1) for v in value]
    return value


def before_send(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    request = event.get("request")
    if isinstance(request, dict) and any(
        str(request.get("url", "")).split("?")[0].endswith(p) for p in SCRUBBED_BODY_PATHS
    ):
        request.pop("data", None)
        request.pop("cookies", None)
        request["headers"] = {k: v for k, v in (request.get("headers") or {}).items() if k.lower() != "authorization"}
    if isinstance(request, dict) and "data" in request:
        request["data"] = _scrub(request["data"])
    for exception in (event.get("exception") or {}).get("values") or []:
        for frame in (exception.get("stacktrace") or {}).get("frames") or []:
            if isinstance(frame.get("vars"), dict):
                frame["vars"] = _scrub(frame["vars"])
    return event
