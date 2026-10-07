"""
Choosing the day's motivation message (X-01.1 W3.3, FR-N9). Pure: the candidates, what the student saw recently and the
date come in as arguments, a message (or the reason there is none) comes out, so every rule is a plain unit test.

The rules:
  * a message never repeats for the same student within `NO_REPEAT_DAYS` days (a message shown on day D can come back
    on day D + 60, not before);
  * the exam phase narrows the pool: a `final_week` line is only a candidate in the last seven days, a line written for
    `any` day fits every day, and a student with no exam date only gets `any` lines;
  * the student's tone is preferred, then relaxed, so a small library still lasts; the order is
      1. their tone, written for this phase     3. any tone, written for this phase
      2. their tone, for any day                4. any tone, for any day
    and the first group that has an unseen message wins;
  * nothing is ever repeated to fill a gap: when every candidate was seen in the last 60 days the answer is
    "exhausted" (and "empty" when the library has nothing for this student at all), and the caller shows or sends nothing.

The pick inside a group is deterministic for a seed (student and day), so a retry or a second caller on the same day
chooses the same line, and different days spread across the group.
"""

from __future__ import annotations

import hashlib
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from .enums import MessagePhase

NO_REPEAT_DAYS = 60


class Shortage(StrEnum):
    EMPTY = "empty"  # no published message fits this student (course, level, language) at all
    EXHAUSTED = "exhausted"  # some fit, but each was shown to them in the last 60 days


@dataclass(frozen=True)
class Candidate:
    """The facts about one published message that the choice needs."""

    id: object
    tone: str
    phase: str  # a `MessagePhase` value


@dataclass(frozen=True)
class Choice:
    candidate: Candidate | None
    shortage: Shortage | None = None


def phase_for(days_left: int | None) -> MessagePhase | None:
    """The phase of an exam `days_left` days away, or None when the student has no upcoming exam date."""
    if days_left is None or days_left < 0:
        return None
    if days_left == 0:
        return MessagePhase.EXAM_DAY
    if days_left <= 7:
        return MessagePhase.FINAL_WEEK
    if days_left <= 30:
        return MessagePhase.NEAR
    return MessagePhase.FAR


def recent_since(today: date) -> date:
    """The earliest day whose message still counts as recent: shown on or after this date means "do not repeat"."""
    return today - timedelta(days=NO_REPEAT_DAYS - 1)


def is_recent(shown_on: date, today: date) -> bool:
    return (today - shown_on).days < NO_REPEAT_DAYS


def _tiers(candidates: Iterable[Candidate], tone: str, phase: MessagePhase | None) -> list[list[Candidate]]:
    pool = list(candidates)
    any_phase = MessagePhase.ANY.value

    def pick(*, same_tone: bool, phase_value: str) -> list[Candidate]:
        return [c for c in pool if c.phase == phase_value and (not same_tone or c.tone == tone)]

    tiers = []
    if phase is not None and phase is not MessagePhase.ANY:
        tiers.append(pick(same_tone=True, phase_value=phase.value))
    tiers.append(pick(same_tone=True, phase_value=any_phase))
    if phase is not None and phase is not MessagePhase.ANY:
        tiers.append(pick(same_tone=False, phase_value=phase.value))
    tiers.append(pick(same_tone=False, phase_value=any_phase))
    return tiers


def _index(seed: str, size: int) -> int:
    return int.from_bytes(hashlib.sha256(seed.encode()).digest()[:8], "big") % size


def choose(
    candidates: Collection[Candidate],
    *,
    recent_ids: Collection[object],
    tone: str,
    phase: MessagePhase | None,
    seed: str,
) -> Choice:
    """The message for this student and day, or why there is none. See the module docstring for the rules."""
    if not candidates:
        return Choice(None, Shortage.EMPTY)
    seen = set(recent_ids)
    for tier in _tiers(candidates, tone, phase):
        unseen = sorted((c for c in tier if c.id not in seen), key=lambda c: str(c.id))
        if unseen:
            return Choice(unseen[_index(seed, len(unseen))])
    return Choice(None, Shortage.EXHAUSTED)
