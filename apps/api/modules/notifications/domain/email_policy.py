"""
Whether the weekly email goes out (X-01.1 W3.5). Pure, and deliberately smaller than the push policy: email has no
quiet hours, no daily cap and no device, because it is one message a week that the student reads when they choose.

Order of the rules is part of the contract:
  1. the event or the whole feature is switched off   -> suppress (flag_off)
  2. the student switched the email channel, or the master switch, off -> suppress (preference)
  3. there is no address to send to                   -> suppress (no_address)
  4. it is past its useful life (a late sweep)        -> suppress (stale)
  5. otherwise                                        -> send
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import SuppressReason


@dataclass(frozen=True)
class EmailPolicyInput:
    now: datetime
    channel_enabled: bool
    has_address: bool
    master_on: bool = True  # the student's master switch for notifications (ERD: it covers push and email)
    event_disabled: bool = False
    expires_at: datetime | None = None


@dataclass(frozen=True)
class EmailDecision:
    send: bool
    reason: SuppressReason | None = None


def decide_email(facts: EmailPolicyInput) -> EmailDecision:
    if facts.event_disabled:
        return EmailDecision(False, SuppressReason.FLAG_OFF)
    if not facts.master_on or not facts.channel_enabled:
        return EmailDecision(False, SuppressReason.PREFERENCE)
    if not facts.has_address:
        return EmailDecision(False, SuppressReason.NO_ADDRESS)
    if facts.expires_at is not None and facts.now >= facts.expires_at:
        return EmailDecision(False, SuppressReason.STALE)
    return EmailDecision(True)
