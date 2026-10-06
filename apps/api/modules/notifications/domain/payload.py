"""
The message a service worker receives (PRD 9.4, version 1). Pure. Built from the stored notification, never from raw
input, so the link has already been checked once and is checked again here. No keys, no student data beyond the text
the student is meant to read. Old workers ignore fields they do not know, so additions stay version 1.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .deeplinks import validate_deep_link

PAYLOAD_VERSION = 1
MAX_PAYLOAD_BYTES = 3 * 1024  # push services accept about 4 KB after encryption overhead


class PayloadTooLarge(ValueError):
    """The encoded payload would not fit in a push message."""


@dataclass(frozen=True)
class PayloadAction:
    id: str
    title: str


def link_with_notification(deep_link: str, notification_id: object) -> str:
    """`/app/focus` -> `/app/focus?n=<id>`. Keeps an existing query and fragment; replaces an old `n`."""
    parts = urlsplit(validate_deep_link(deep_link))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != "n"]
    query.append(("n", str(notification_id)))
    return urlunsplit(("", "", parts.path, urlencode(query), parts.fragment))


def build_payload(
    *,
    notification_id: object,
    category: str,
    title: str,
    body: str,
    tag: str,
    deep_link: str,
    actions: Sequence[PayloadAction] = (),
) -> dict:
    return {
        "v": PAYLOAD_VERSION,
        "id": str(notification_id),
        "category": category,
        "title": title,
        "body": body,
        "tag": tag,
        "url": link_with_notification(deep_link, notification_id),
        "actions": [{"id": action.id, "title": action.title} for action in actions],
    }


def encode_payload(payload: dict) -> str:
    """Compact JSON (UTF-8 under 3 KB) or `PayloadTooLarge`."""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode()) > MAX_PAYLOAD_BYTES:
        raise PayloadTooLarge(f"Payload is larger than {MAX_PAYLOAD_BYTES} bytes.")
    return text


EXEMPT_TTL_SECONDS = 5 * 60  # a round-end alert is useless after 5 minutes (matches policy.EXEMPT_STALE_AFTER)
DEFAULT_TTL_SECONDS = 60 * 60
MAX_TTL_SECONDS = 24 * 60 * 60
_URGENCY_BY_PRIORITY = {0: "high", 1: "normal", 2: "low", 3: "very-low"}


def delivery_window(priority: int, now: datetime, expires_at: datetime | None) -> tuple[int, str]:
    """
    How long the push service may hold the message for an offline phone, and the `Urgency` header. Timer alerts are
    high urgency and short-lived; a daily nudge may wait and does not wake a phone that is saving battery.
    """
    if expires_at is not None:
        ttl = int((expires_at - now).total_seconds())
    else:
        ttl = EXEMPT_TTL_SECONDS if priority == 0 else DEFAULT_TTL_SECONDS
    return max(1, min(ttl, MAX_TTL_SECONDS)), _URGENCY_BY_PRIORITY.get(priority, "normal")
