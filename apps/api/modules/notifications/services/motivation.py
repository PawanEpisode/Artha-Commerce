"""
Writes for the motivation library (X-01.1 W3.3): publishing and retiring lines (the Django admin calls these, so the
rules are not in the admin), checking a line before it can go live, and loading the seed files as drafts.

Nothing here sends anything. A draft is never picked; a line goes live only through `publish`, after an editor has read it.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from modules.syllabus import selectors as syllabus_selectors

from ..domain.enums import MessagePhase, MessageStatus, Tone, values
from ..models import Message

BODY_MAX = 240  # the column
BODY_ADVISED = 100  # reads whole on a lock screen; the seed keeps to it, the admin only warns


def problems(message: Message) -> list[str]:
    """Reasons this line cannot go live. Empty means it may be published."""
    found = []
    body = (message.body or "").strip()
    if not body:
        found.append("The text is empty.")
    if len(body) > BODY_MAX:
        found.append(f"The text is longer than {BODY_MAX} characters.")
    if message.attribution is not None and len(message.attribution) > 80:
        found.append("The attribution is longer than 80 characters.")
    if message.level_id and message.course_id and message.level.course_id != message.course_id:
        found.append("The level does not belong to the course.")
    return found


@dataclass(frozen=True)
class Review:
    changed: int
    refused: dict[str, list[str]]  # message id -> reasons it could not be published


def publish(messages: Iterable[Message], *, now: datetime | None = None) -> Review:
    """Publish drafts and retired lines that pass `problems`. Already published lines are left alone."""
    now = now or timezone.now()
    changed = 0
    refused: dict[str, list[str]] = {}
    with transaction.atomic():
        for message in messages:
            if message.status == MessageStatus.PUBLISHED:
                continue
            reasons = problems(message)
            if reasons:
                refused[str(message.pk)] = reasons
                continue
            message.body = message.body.strip()
            message.status = MessageStatus.PUBLISHED
            message.published_at = now
            message.save(update_fields=["body", "status", "published_at", "updated_at"])
            changed += 1
    return Review(changed, refused)


def retire(messages: Iterable[Message]) -> int:
    """Stop using published lines. Students keep the history of what they were shown. Returns how many changed."""
    changed = 0
    with transaction.atomic():
        for message in messages:
            if message.status != MessageStatus.PUBLISHED:
                continue
            message.status = MessageStatus.RETIRED
            message.save(update_fields=["status", "updated_at"])
            changed += 1
    return changed


# --- seed files -----------------------------------------------------------------------------------------------------


class SeedError(ValueError):
    """A seed file that cannot be loaded as written."""


@dataclass
class SeedResult:
    created: int = 0
    existing: int = 0
    skipped: list[str] = field(default_factory=list)  # entries whose course or level is not in the database yet

    def __iadd__(self, other: SeedResult) -> SeedResult:
        self.created += other.created
        self.existing += other.existing
        self.skipped += other.skipped
        return self


def _entry(raw: dict, where: str) -> tuple[str, str, str, str, str | None]:
    try:
        key, body, tone, phase = raw["key"], raw["body"], raw["tone"], raw.get("phase", MessagePhase.ANY.value)
    except (KeyError, TypeError):
        raise SeedError(f"{where}: every message needs key, body and tone.") from None
    if not isinstance(key, str) or not key or len(key) > 60:
        raise SeedError(f"{where}: key {key!r} must be 1 to 60 characters.")
    if not isinstance(body, str) or not body.strip() or len(body.strip()) > BODY_MAX:
        raise SeedError(f"{where}: {key}: the text must be 1 to {BODY_MAX} characters.")
    if tone not in values(Tone):
        raise SeedError(f"{where}: {key}: unknown tone {tone!r}.")
    if phase not in values(MessagePhase):
        raise SeedError(f"{where}: {key}: unknown phase {phase!r}.")
    attribution = raw.get("attribution")
    if attribution is not None and (not isinstance(attribution, str) or len(attribution) > 80):
        raise SeedError(f"{where}: {key}: the attribution must be text of at most 80 characters.")
    return key, body.strip(), tone, phase, attribution


def load_seed(data: dict, *, source: str = "seed") -> SeedResult:
    """
    Load one seed file ({"course": code|null, "level": code|null, "messages": [...]}) as drafts. Idempotent: a line
    already loaded (same `key`) is left exactly as it is, so an editor's changes, publication or retirement survive
    a second run. Never publishes. A file naming a course or level that is not in the database yet is skipped whole
    and reported, so the command can be run again once the syllabus is loaded.
    """
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list) or not data["messages"]:
        raise SeedError(f"{source}: expected an object with a non-empty 'messages' list.")
    entries = [_entry(raw, source) for raw in data["messages"]]
    keys = [entry[0] for entry in entries]
    if len(set(keys)) != len(keys):
        raise SeedError(f"{source}: duplicate keys.")

    course = level = None
    if data.get("level") and not data.get("course"):
        raise SeedError(f"{source}: a level needs its course code.")
    if data.get("course"):
        course = syllabus_selectors.get_course(data["course"])
        if course is None:
            return SeedResult(skipped=[f"{source}: course {data['course']!r} is not loaded"])
    if data.get("level"):
        level = syllabus_selectors.get_level(data["course"], data["level"])
        if level is None:
            return SeedResult(skipped=[f"{source}: level {data['course']}/{data['level']} is not loaded"])

    have = set(Message.objects.filter(seed_key__in=keys).values_list("seed_key", flat=True))
    result = SeedResult(existing=len(have))
    fresh = [
        Message(
            seed_key=key,
            body=body,
            tone=tone,
            phase=phase,
            attribution=attribution,
            course=course,
            level=level,
            status=MessageStatus.DRAFT,
        )
        for key, body, tone, phase, attribution in entries
        if key not in have
    ]
    Message.objects.bulk_create(fresh)
    result.created = len(fresh)
    return result
