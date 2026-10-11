"""
Keeping recall identifiers out of logs and error reports. A card id in a URL (`/recall/cards/<uuid>/`) says which card a student
was working on, so recall URLs are masked wherever the API itself writes or sends one: Sentry (`core.sentry`) and the `django.request`
logger (the 4xx and 5xx lines). Host, platform and dev-server access logs are outside the API.
"""

from __future__ import annotations

import logging
import re

RECALL_SEGMENT = "/recall/"
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def mask_ids(text):
    """Replaces every UUID in a string with `{id}`; anything else is returned as it is."""
    return _UUID.sub("{id}", text) if isinstance(text, str) else text


class MaskRecallIds(logging.Filter):
    """Log filter: a record that mentions a recall URL gets its ids masked and its `request` object dropped (it holds the path)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - a malformed record must still be logged, as it is
            return True
        if RECALL_SEGMENT in message:
            record.msg, record.args = mask_ids(message), ()
            if hasattr(record, "request"):
                record.request = None
        return True
