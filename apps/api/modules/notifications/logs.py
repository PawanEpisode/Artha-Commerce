"""Structured log lines (PRD section 10): `name key=value ...`, with the same fields on the record as `record.push`."""

from __future__ import annotations

import logging

logger = logging.getLogger("modules.notifications")


def log_event(level: int, name: str, *, source: logging.Logger | None = None, **fields: object) -> None:
    """One structured line. Callers pass only the fields PRD section 10 lists: never an endpoint, key or body."""
    (source or logger).log(
        level, "%s %s", name, " ".join(f"{k}={v}" for k, v in fields.items() if v is not None), extra={"push": fields}
    )
