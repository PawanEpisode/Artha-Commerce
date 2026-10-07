"""
How long each notifications table keeps its rows (PRD FR-N24, ERD section on retention). Pure: dates in, cutoffs out.

Action tokens (W3.6) do not exist yet; their rule joins this table with its wave. The shown-message memory (W3.3)
is kept for 120 days though the no-repeat rule only reads the last 60, so a change of that rule needs no backfill. Delivery rows are the audit trail, so they outlive the notification text by nothing: a notification's deliveries
go with it, and older deliveries go on their own after 90 days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

BATCH_SIZE = 1000  # rows per delete; the lock is held for one batch only (FR-N24: never longer than about a second)

DELIVERY_DAYS = 90  # after `attempted_at`
NOTIFICATION_DAYS = 180  # after `created_at` (the inbox shows the last 50)
JOB_DAYS = 30  # jobs that are not pending, after `updated_at`
REVOKED_DEVICE_DAYS = 30  # after `revoked_at`
MESSAGE_SHOWN_DAYS = 120  # after `shown_on` (the 60 day no-repeat rule reads only the last 60)


@dataclass(frozen=True)
class Cutoffs:
    deliveries: datetime
    notifications: datetime
    jobs: datetime
    revoked_devices: datetime
    messages_shown: date


def cutoffs(now: datetime) -> Cutoffs:
    """Rows older than these moments are pruned."""
    return Cutoffs(
        deliveries=now - timedelta(days=DELIVERY_DAYS),
        notifications=now - timedelta(days=NOTIFICATION_DAYS),
        jobs=now - timedelta(days=JOB_DAYS),
        revoked_devices=now - timedelta(days=REVOKED_DEVICE_DAYS),
        messages_shown=(now - timedelta(days=MESSAGE_SHOWN_DAYS)).date(),
    )
