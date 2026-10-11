"""
Sentry hooks. Bodies of endpoints that carry a token or behavioural data never leave the API. Recall (F-15) is stricter: card text,
card ids, review events and search text can be personal notes or study habits, so nothing a recall request carries reaches Sentry.
"""

from typing import Any
from urllib.parse import urlsplit

from core.privacy import RECALL_SEGMENT, mask_ids

#: Paths whose request body is dropped from every event (the beacon body holds an access token; a notification button
#: carries its one-time token).
SCRUBBED_BODY_PATHS = ("/me/last-visit/", "/notifications/actions/", "/unlock/")
#: Keys whose values are replaced wherever they appear in request data or local variables.
SCRUBBED_KEYS = frozenset({"token", "password", "secret"})
FILTERED = "[Filtered]"
_RECALL_CODE = ("modules.recall", "modules/recall")


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
    _drop_recall_locals(event)
    if _is_recall_event(event):
        _scrub_recall(event)
    return event


def _is_recall_url(url: Any) -> bool:
    return RECALL_SEGMENT in urlsplit(str(url or "")).path


def _is_recall_event(event: dict[str, Any]) -> bool:
    """A recall request, by its URL (set by the WSGI layer) or by its route (set by the Django integration), or an error raised
    inside the recall modules (a tick, a command, a task) whatever started it."""
    request = event.get("request")
    if isinstance(request, dict) and _is_recall_url(request.get("url")):
        return True
    route = str(event.get("transaction") or "")
    if RECALL_SEGMENT in route or route.startswith("recall/") or "modules.recall" in route:
        return True
    return any(
        _is_recall_frame(frame)
        for exception in (event.get("exception") or {}).get("values") or []
        for frame in (exception.get("stacktrace") or {}).get("frames") or []
    )


def _is_recall_frame(frame: dict[str, Any]) -> bool:
    where = f"{frame.get('module', '')} {frame.get('abs_path', '')} {frame.get('filename', '')}"
    return any(marker in where for marker in _RECALL_CODE)


def _scrub_recall(event: dict[str, Any]) -> None:
    """Drops everything a recall request carries: body, query string (search text), ids in the URL, locals, breadcrumbs."""
    request = event.get("request")
    if isinstance(request, dict):
        for key in ("data", "cookies", "query_string"):
            request.pop(key, None)
        if request.get("url"):
            request["url"] = mask_ids(urlsplit(str(request["url"]))._replace(query="", fragment="").geturl())
        request["headers"] = {k: v for k, v in (request.get("headers") or {}).items() if k.lower() != "authorization"}
    for key in ("breadcrumbs", "extra"):
        event.pop(key, None)
    for key in ("transaction", "message"):
        if key in event:
            event[key] = mask_ids(event[key])
    if isinstance(event.get("logentry"), dict):
        event["logentry"] = {k: mask_ids(v) for k, v in event["logentry"].items() if k != "params"}
    for exception in (event.get("exception") or {}).get("values") or []:
        exception["value"] = mask_ids(exception.get("value"))
        for frame in (exception.get("stacktrace") or {}).get("frames") or []:
            frame.pop("vars", None)
    for span in event.get("spans") or []:
        span.pop("data", None)
        span["description"] = mask_ids(span.get("description"))


def _drop_recall_locals(event: dict[str, Any]) -> None:
    """Frames inside the recall modules never send their local variables (card fields, selections), whatever the request was."""
    for exception in (event.get("exception") or {}).get("values") or []:
        for frame in (exception.get("stacktrace") or {}).get("frames") or []:
            if _is_recall_frame(frame):
                frame.pop("vars", None)


def before_send_transaction(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Performance events carry the request URL and the route too, so they get the same recall treatment."""
    return before_send(event, hint)
