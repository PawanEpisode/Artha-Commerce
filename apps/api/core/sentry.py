"""Sentry hooks. Bodies of endpoints that carry a token or behavioural data never leave the API."""

from typing import Any

#: Paths whose request body is dropped from every event (the beacon body holds an access token).
SCRUBBED_BODY_PATHS = ("/me/last-visit/",)


def before_send(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    request = event.get("request")
    if isinstance(request, dict) and any(
        str(request.get("url", "")).split("?")[0].endswith(p) for p in SCRUBBED_BODY_PATHS
    ):
        request.pop("data", None)
        request.pop("cookies", None)
        request["headers"] = {k: v for k, v in (request.get("headers") or {}).items() if k.lower() != "authorization"}
    return event
