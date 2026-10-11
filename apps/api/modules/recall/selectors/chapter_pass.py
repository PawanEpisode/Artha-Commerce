"""
Reads for the chapter recall pass (FR-F15-64). Pure reads: the counts the rule in `domain.chapter_pass` needs, which chapters a
session touched, and when a pass was last announced for a chapter (from the sessions, no extra table).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from ..domain import chapter_pass as rule
from ..models import RecallCard, RecallReviewLog, RecallSession


def _set(user_id, chapter_id):
    """Her active mandatory and important cards of the chapter: the set the pass is counted over."""
    return RecallCard.objects.filter(
        user_id=user_id,
        chapter_id=chapter_id,
        status="active",
        deleted_at__isnull=True,
        importance__gte=rule.MIN_IMPORTANCE,
    )


def pass_state(user_id, chapter_id: UUID, *, now: datetime) -> rule.PassResult:
    """The set size and how many of its cards were reviewed Hard or better in the last 7 days (two counts, no card rows)."""
    members = _set(user_id, chapter_id)
    size = members.count()
    if size < rule.MIN_SET:
        return rule.evaluate(size, 0)
    undone = RecallReviewLog.objects.filter(user_id=user_id, kind="undo").values("voids_id")
    ok = (
        RecallReviewLog.objects.filter(
            user_id=user_id,
            kind="review",
            rating__gte=2,
            reviewed_at__gt=now - rule.WINDOW,
            reviewed_at__lte=now,
            card_id__in=members.values("id"),
        )
        .exclude(id__in=undone)
        .values("card_id")
        .distinct()
        .count()
    )
    return rule.evaluate(size, ok)


def chapters_of_session(user_id, session_id: UUID) -> list[UUID]:
    """The chapters a session's reviews (undone ones left out) touched, in id order. Unsorted cards have none."""
    undone = RecallReviewLog.objects.filter(user_id=user_id, kind="undo").values("voids_id")
    cards = (
        RecallReviewLog.objects.filter(user_id=user_id, session_id=session_id, kind="review")
        .exclude(id__in=undone)
        .values("card_id")
    )
    ids = (
        RecallCard.objects.filter(user_id=user_id, id__in=cards, chapter_id__isnull=False)
        .values_list("chapter_id", flat=True)
        .distinct()
    )
    return sorted(ids, key=str)


def last_pass_at(
    user_id, chapter_id: UUID, *, now: datetime, exclude_session_id: UUID | None = None
) -> datetime | None:
    """When a pass of this chapter was last announced, looking back one cool-down and a day (older ones cannot block)."""
    since = now - rule.COOLDOWN - timedelta(days=1)
    qs = RecallSession.objects.filter(user_id=user_id, started_at__gte=since)
    if exclude_session_id is not None:
        qs = qs.exclude(pk=exclude_session_id)
    wanted = str(chapter_id)
    latest: datetime | None = None
    for passes in qs.values_list("chapter_passes", flat=True):
        for entry in passes or ():
            if entry.get("chapter_id") != wanted:
                continue
            at = datetime.fromisoformat(entry["at"])
            if latest is None or at > latest:
                latest = at
    return latest
