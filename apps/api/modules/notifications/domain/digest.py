"""
The daily digest (X-01.1 W3.7, FR-N34). A student who accepted "Switch to a daily digest" stops getting separate
pushes for everything except the timer; those notifications still land in the inbox, and once a day, at their nudge
time, one push says what the day holds and what is waiting. Pure: facts in, words and a link out.

What it says, in this order: an exam milestone on its exact day, the chapters due for revision, and the unread inbox
items. A day with none of the three sends nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

INBOX_LINK = "/app/notifications"
REVISION_LINK = "/app/revision"
HOME_LINK = "/app"
#: Categories a student on the digest keeps getting pushes for: the timer, which answers their own running round.
KEEP_PUSH = frozenset({"timer"})


@dataclass(frozen=True)
class DigestFacts:
    unread: int  # unread items in the inbox
    due_count: int  # chapters due for revision today
    milestone: int | None  # days to the exam when today is a milestone day, else None


def worth_sending(facts: DigestFacts) -> bool:
    return bool(facts.unread or facts.due_count or facts.milestone)


def context_for(facts: DigestFacts, local_date: str) -> dict[str, Any]:
    return {
        "unread": facts.unread,
        "due_count": facts.due_count,
        "milestone": facts.milestone,
        "local_date": local_date,
    }


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def digest_lines(context: Mapping[str, Any]) -> tuple[list[str], str]:
    """The sentences of the digest and where it opens: the inbox when something is unread, else revision, else home."""
    unread = int(context.get("unread") or 0)
    due = int(context.get("due_count") or 0)
    milestone = context.get("milestone")
    lines: list[str] = []
    if milestone:
        days = int(milestone)
        lines.append("Your exam is tomorrow." if days == 1 else f"{days} days to your exam.")
    if due:
        lines.append(f"{_plural(due, 'chapter')} due for revision.")
    if unread:
        lines.append(f"{_plural(unread, 'update')} in your inbox.")
    link = INBOX_LINK if unread else REVISION_LINK if due else HOME_LINK
    return lines or ["Nothing new today."], link
