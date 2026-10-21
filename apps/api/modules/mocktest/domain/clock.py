"""
Server-authoritative clock and phase derivation for F-08 Mock Tests.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, NamedTuple


GRACE_SECONDS = 120
SECTION_GRACE_SECONDS = 15


class ClockState(NamedTuple):
    phase: str
    remaining_ms: int
    section_remaining_ms: int | None
    server_time: datetime
    active_section_key: str | None
    auto_submit_due: bool
    upload_due: bool


def calculate_extra_seconds(duration_seconds: int, time_extension_pct: int) -> int:
    """Extra time accommodation: ceil(duration_seconds * pct / 100)."""
    if time_extension_pct <= 0:
        return 0
    return math.ceil(duration_seconds * time_extension_pct / 100)


def state_at(
    *,
    phase: str,
    instructions_accepted_at: datetime | None,
    reading_seconds: int,
    reading_ends_at: datetime | None,
    writing_started_at: datetime | None,
    writing_ends_at: datetime | None,
    upload_until: datetime | None,
    duration_seconds: int,
    extra_seconds: int,
    paused_seconds: int,
    is_paused: bool,
    now: datetime,
    sections: list[dict[str, Any]] | None = None,
    section_timing: str = "none",
) -> ClockState:
    """
    Pure function to derive clock state and phase at a given timestamp `now`.
    Does not mutate anything.
    """
    # If already done or abandoned, stay done/abandoned
    if phase in ("done", "abandoned"):
        return ClockState(
            phase=phase,
            remaining_ms=0,
            section_remaining_ms=0,
            server_time=now,
            active_section_key=None,
            auto_submit_due=False,
            upload_due=False,
        )

    # 1. Instructions phase
    if phase == "instructions":
        if instructions_accepted_at is None:
            return ClockState(
                phase="instructions",
                remaining_ms=(duration_seconds + extra_seconds) * 1000,
                section_remaining_ms=None,
                server_time=now,
                active_section_key=None,
                auto_submit_due=False,
                upload_due=False,
            )
        # Instructions were accepted, see if reading time applies
        if reading_seconds > 0:
            rend = reading_ends_at or (instructions_accepted_at + timedelta(seconds=reading_seconds))
            if now < rend:
                rem_read = max(0, int((rend - now).total_seconds() * 1000))
                return ClockState(
                    phase="reading",
                    remaining_ms=rem_read,
                    section_remaining_ms=None,
                    server_time=now,
                    active_section_key=None,
                    auto_submit_due=False,
                    upload_due=False,
                )

    # 2. Reading phase
    if phase == "reading":
        rend = reading_ends_at or (
            instructions_accepted_at + timedelta(seconds=reading_seconds)
            if instructions_accepted_at
            else now
        )
        if now < rend:
            rem_read = max(0, int((rend - now).total_seconds() * 1000))
            return ClockState(
                phase="reading",
                remaining_ms=rem_read,
                section_remaining_ms=None,
                server_time=now,
                active_section_key=None,
                auto_submit_due=False,
                upload_due=False,
            )
        # Reading period ended -> transitions to writing
        phase = "writing"
        if writing_started_at is None:
            writing_started_at = rend
        if writing_ends_at is None:
            writing_ends_at = writing_started_at + timedelta(
                seconds=(duration_seconds + extra_seconds + paused_seconds)
            )

    # 3. Writing phase
    if phase == "writing":
        w_end = writing_ends_at
        if w_end is None and writing_started_at is not None:
            w_end = writing_started_at + timedelta(
                seconds=(duration_seconds + extra_seconds + paused_seconds)
            )

        if w_end is not None:
            # Overdue past grace -> auto-submit due
            grace_deadline = w_end + timedelta(seconds=GRACE_SECONDS)
            if now > grace_deadline:
                return ClockState(
                    phase="writing",
                    remaining_ms=0,
                    section_remaining_ms=0,
                    server_time=now,
                    active_section_key=None,
                    auto_submit_due=True,
                    upload_due=False,
                )

            remaining_ms = max(0, int((w_end - now).total_seconds() * 1000))
        else:
            remaining_ms = (duration_seconds + extra_seconds) * 1000

        # Section remaining time
        sec_rem_ms = None
        active_sec = None

        if sections:
            for sec in sections:
                if sec.get("status") == "open":
                    active_sec = sec.get("key")
                    closes_at = sec.get("closes_at")
                    if closes_at and section_timing == "sequential":
                        sec_rem_ms = max(0, int((closes_at - now).total_seconds() * 1000))
                    break

        return ClockState(
            phase="writing",
            remaining_ms=remaining_ms,
            section_remaining_ms=sec_rem_ms,
            server_time=now,
            active_section_key=active_sec,
            auto_submit_due=False,
            upload_due=False,
        )

    # 4. Upload phase
    if phase == "upload":
        if upload_until is not None and now > upload_until:
            return ClockState(
                phase="upload",
                remaining_ms=0,
                section_remaining_ms=None,
                server_time=now,
                active_section_key=None,
                auto_submit_due=False,
                upload_due=True,  # upload window ended -> move to done
            )
        rem_upload = max(0, int((upload_until - now).total_seconds() * 1000)) if upload_until else 0
        return ClockState(
            phase="upload",
            remaining_ms=rem_upload,
            section_remaining_ms=None,
            server_time=now,
            active_section_key=None,
            auto_submit_due=False,
            upload_due=False,
        )

    return ClockState(
        phase=phase,
        remaining_ms=0,
        section_remaining_ms=None,
        server_time=now,
        active_section_key=None,
        auto_submit_due=False,
        upload_due=False,
    )
