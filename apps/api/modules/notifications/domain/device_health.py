"""
When to give up on a device. A push service that says the subscription is gone (404 or 410) ends it at once; other
failures only end it after a sustained run, so a phone that is merely offline for a day keeps its subscription.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .enums import RevokeReason

GONE_STATUSES = frozenset({404, 410})
REVOKE_AFTER_FAILURES = 5
REVOKE_AFTER_AGE = timedelta(days=7)


@dataclass(frozen=True)
class Health:
    consecutive_failures: int = 0
    first_failure_at: datetime | None = None


@dataclass(frozen=True)
class HealthChange:
    health: Health
    revoke: RevokeReason | None = None


def on_success() -> Health:
    """A delivery that the push service accepted clears the failure run."""
    return Health()


def on_failure(health: Health, now: datetime, http_status: int | None) -> HealthChange:
    """Call once per notification that failed after its retries, not once per retry."""
    failures = health.consecutive_failures + 1
    first = health.first_failure_at or now
    updated = Health(failures, first)
    if http_status in GONE_STATUSES:
        return HealthChange(updated, RevokeReason.GONE)
    if failures >= REVOKE_AFTER_FAILURES and now - first >= REVOKE_AFTER_AGE:
        return HealthChange(updated, RevokeReason.FAILURES)
    return HealthChange(updated)
