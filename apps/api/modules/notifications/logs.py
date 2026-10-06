"""Structured log lines (PRD section 10): `name key=value ...`, with the same fields on the record as `record.push`."""

from __future__ import annotations

import logging

import sentry_sdk

logger = logging.getLogger("modules.notifications")


def log_event(level: int, name: str, *, source: logging.Logger | None = None, **fields: object) -> None:
    """One structured line. Callers pass only the fields PRD section 10 lists: never an endpoint, key or body."""
    # Sentry tags (FR-N23): every line is tagged with its name, and with the notification event it belongs to, so an
    # alert rule or a filter can pick "push_failed" or one event type. The scope lasts for this one call.
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("push_log", name)
        if fields.get("event") is not None:
            scope.set_tag("notification_event", str(fields["event"]))
        (source or logger).log(
            level,
            "%s %s",
            name,
            " ".join(f"{k}={v}" for k, v in fields.items() if v is not None),
            extra={"push": fields},
        )
