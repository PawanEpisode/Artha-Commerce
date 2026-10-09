"""
The forgotten list (FR-F15-60, ERD Q-5): score = (lapses in the last 30 days times 2 + Again ratings in the last 14) times the
importance weight. A lapse is an Again on a card in the review phase. Reviews that were undone, or did not count, are ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Count, Max, Q

from ..domain import limits as lim
from ..domain.scheduling import forgetting_score, is_forgotten
from ..models import RecallCard, RecallReviewLog

AGAIN_WINDOW = lim.FORGOTTEN_AGAIN_WINDOW_DAYS
CANDIDATE_CAP = 500


@dataclass(frozen=True)
class ForgottenRow:
    card: RecallCard
    score: float
    lapses: int
    agains: int
    last_again_at: datetime


def forgotten(
    user_id,
    *,
    now: datetime,
    window_days: int = lim.FORGOTTEN_LAPSE_WINDOW_DAYS,
    limit: int = 20,
    subject_key: str | None = None,
) -> list[ForgottenRow]:
    since = now - timedelta(days=window_days)
    recent = now - timedelta(days=AGAIN_WINDOW)
    undone = RecallReviewLog.objects.filter(user_id=user_id, kind="undo").values("voids_id")
    stats = (
        RecallReviewLog.objects.filter(
            user_id=user_id,
            kind="review",
            rating=1,
            counts_for_scheduling=True,
            reviewed_at__gte=since,
            reviewed_at__lte=now,
        )
        .exclude(id__in=undone)
        .values("card_id")
        .annotate(
            lapses=Count("id", filter=Q(phase_before=2)),
            agains=Count("id", filter=Q(reviewed_at__gte=recent)),
            last=Max("reviewed_at"),
        )
    )
    by_card = {r["card_id"]: r for r in stats[: CANDIDATE_CAP * 4]}
    if not by_card:
        return []
    cards = RecallCard.objects.select_related("item", "item_version").filter(
        user_id=user_id, id__in=list(by_card), status="active", deleted_at__isnull=True
    )
    if subject_key:
        cards = cards.filter(subject_key=subject_key)
    rows = []
    for c in cards:
        r = by_card[c.id]
        if not is_forgotten(r["lapses"], r["agains"]):
            continue
        weight = lim.IMPORTANCE_WEIGHTS[min(max(c.importance, 0), 2)]
        rows.append(
            ForgottenRow(c, forgetting_score(r["lapses"], r["agains"]) * weight, r["lapses"], r["agains"], r["last"])
        )
    rows.sort(key=lambda r: (-r.score, -r.last_again_at.timestamp(), str(r.card.id)))
    return rows[: max(1, min(limit, 50))]
