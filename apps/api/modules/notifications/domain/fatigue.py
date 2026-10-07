"""
Fatigue control (X-01.1 FR-N34, W3.7). Pure: the student's recent pushes and the date of the last offer in, whether to
offer "Switch to a daily digest" out.

The rule, exactly:
  * look at the last five pushes that count towards the daily cap (so timer alerts, which are answered by acting on the
    timer and never count, and the test push are left out), one per notification however many devices got it;
  * all five are unclicked (a click on any of them, from the notification or the inbox, resets the run);
  * they fall on at least three different days in the student's own time zone;
  * the offer was not made in the last 30 days, and the student is not on the digest already.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from .quiet_hours import local_date

RUN_LENGTH = 5
MIN_DAYS = 3
OFFER_EVERY = timedelta(days=30)


@dataclass(frozen=True)
class PushFact:
    """One push the student received: when it was sent, and whether they ever opened it."""

    sent_at: datetime
    clicked: bool


def should_offer(
    recent: Sequence[PushFact],
    *,
    offered_at: datetime | None,
    digest_on: bool,
    now: datetime,
    tz: str,
) -> bool:
    """`recent` is newest first. Only its first `RUN_LENGTH` entries matter."""
    if digest_on:
        return False
    if offered_at is not None and now - offered_at < OFFER_EVERY:
        return False
    run = list(recent[:RUN_LENGTH])
    if len(run) < RUN_LENGTH or any(push.clicked for push in run):
        return False
    return len({local_date(push.sent_at, tz) for push in run}) >= MIN_DAYS
