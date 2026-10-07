"""
The day's motivation message (X-01.1 W3.3, FR-N9): one per student per local day, shared by the thought card and the
nudge push. Whoever asks first picks it and records it in `messageshown` (unique per student and day); everyone after
gets the same row, so reloading the page, opening a second tab or a push arriving later never shows a second message.

The rules of the choice (phase, tone, the 60 day no-repeat) live in `domain.motivation`; this module reads the facts,
asks it, and writes the one row. When nothing may be shown (an empty library, or every line seen in the last 60 days)
it writes nothing and says so in a log line editors can alert on, rather than repeat a line.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from django.db import IntegrityError, transaction
from django.utils import timezone

from .. import selectors
from ..domain import motivation
from ..domain.catalogue import Category, is_enabled
from ..domain.enums import Channel, ShownChannel
from ..domain.quiet_hours import local_date as local_date_of
from ..logs import log_event
from ..models import Message, MessageShown
from ..selectors import motivation as motivation_selectors


@dataclass(frozen=True)
class Reservation:
    """The student's message for a local day. `created` is False when someone had already picked it."""

    shown: MessageShown
    created: bool

    @property
    def message(self) -> Message:
        return self.shown.message


@dataclass(frozen=True)
class Thought:
    """What the page shows."""

    id: str
    body: str
    attribution: str | None
    shown_on: date


def reserve_message(
    user_id, *, local_date: date, tone: str, channel: ShownChannel, now: datetime | None = None
) -> Reservation | None:
    """
    The student's message for `local_date`: the one already recorded, else a new pick, recorded now. None when nothing
    may be shown (nothing is recorded then). Safe under a race: the unique day key lets one writer win and the loser
    reads the winner's row.
    """
    existing = motivation_selectors.shown_on(user_id, local_date)
    if existing is not None:
        return Reservation(existing, False)

    context = motivation_selectors.student_context(user_id, local_date)
    choice = motivation.choose(
        motivation_selectors.candidates(context),
        recent_ids=motivation_selectors.recently_shown_ids(user_id, local_date),
        tone=tone,
        phase=context.phase,
        seed=f"{user_id}:{local_date.isoformat()}",
    )
    if choice.candidate is None:
        log_event(logging.INFO, "motivation_unavailable", reason=choice.shortage.value, channel=channel.value)
        return None

    message = Message.objects.get(pk=choice.candidate.id)
    try:
        with transaction.atomic():
            shown = MessageShown.objects.create(user_id=user_id, message=message, shown_on=local_date, channel=channel)
    except IntegrityError:
        winner = motivation_selectors.shown_on(user_id, local_date)
        if winner is None:
            raise  # not the day key: a real error
        return Reservation(winner, False)
    shown.message = message
    return Reservation(shown, True)


def todays_thought(user_id, *, now: datetime | None = None) -> Thought | None:
    """
    The card for the student's first open of their local day, and the same one on every reload that day. None when the
    student switched the "Daily thought" category off for the app, or when there is nothing new to show.
    """
    now = now or timezone.now()
    if not is_enabled(Category.MOTIVATION, Channel.INBOX, selectors.overrides(user_id)):
        return None
    prefs = selectors.get_settings(user_id)
    reservation = reserve_message(
        user_id,
        local_date=local_date_of(now, prefs.timezone),
        tone=prefs.nudge_tone,
        channel=ShownChannel.INAPP,
        now=now,
    )
    if reservation is None:
        return None
    message = reservation.message
    return Thought(
        id=str(reservation.shown.id),
        body=message.body,
        attribution=message.attribution or None,
        shown_on=reservation.shown.shown_on,
    )
