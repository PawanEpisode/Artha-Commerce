"""
Catch-up rebalance (ERD 3.5). Overdue and due-today reviews are ranked by risk; the most at-risk `reviews_per_day` stay today
and the rest are spread over the next days at that many per day with a `postpone` event (reason `rebalance`). Mandatory cards
whose retrievability fell below 0.7 are never moved. Cards past the end of the window stay where they are.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from ..domain import limits as lim
from ..domain.fsrs6 import retrievability
from ..domain.scheduling import CardView, end_of_study_day, local_date_of, overdue_days, priority, study_day_start
from ..models import RecallCard, RecallScheduleEvent
from . import engine

CANDIDATE_CAP = 5000


def rebalance(user_id, days: int = lim.REBALANCE_DEFAULT_DAYS, *, now: datetime | None = None) -> dict:
    now = now or timezone.now()
    days = max(1, min(int(days), lim.REBALANCE_MAX_DAYS_AHEAD))
    eng = engine.load(user_id)
    s = eng.settings
    cap = s.reviews_per_day
    today = local_date_of(now, s.tz, s.day_start_hour)
    horizon = end_of_study_day(now, s.tz, s.day_start_hour)
    w20 = eng.weights[20]
    with transaction.atomic():
        cards = list(
            RecallCard.objects.select_for_update(of=("self",))
            .filter(user_id=user_id, status="active", state__gt=0, due_at__lt=horizon)
            .order_by("id")[:CANDIDATE_CAP]
        )
        ranked: list[tuple[float, RecallCard, bool]] = []
        for c in cards:
            elapsed = (
                max(0.0, (now - c.last_review_at).total_seconds() / lim.SECONDS_PER_DAY) if c.last_review_at else 0.0
            )
            r = retrievability(c.stability, elapsed, w20) if c.stability else 1.0
            view = CardView(
                str(c.id), c.subject_key or "", c.importance, c.state, c.stability, c.last_review_at, c.due_at
            )
            protected = c.importance == 2 and r < lim.REBALANCE_PROTECT_R
            ranked.append((priority(c.importance, r, overdue_days(view, now)), c, protected))
        ranked.sort(key=lambda t: (-t[0], str(t[1].id)))
        stay = [c for _, c, protected in ranked if protected]
        movable = [c for _, c, protected in ranked if not protected]
        room = max(0, cap - len(stay))
        stay += movable[:room]
        rest = movable[room:]
        per_day = [0] * days
        moved = 0
        for i, card in enumerate(rest):
            slot = i // cap
            if slot >= days:
                stay.append(card)
                continue
            target = study_day_start(today + timedelta(days=slot + 1), s.tz, s.day_start_hour)
            RecallScheduleEvent.objects.create(
                user_id=user_id,
                card=card,
                kind="postpone",
                at=now,
                from_due=card.due_at,
                to_due=target,
                reason_code="rebalance",
                ref=f"rebalance:{today.isoformat()}",
            )
            card.postponed_until = target
            card.due_at = max(card.due_scheduled_at or target, target)
            card.rev += 1
            card.save(update_fields=["postponed_until", "due_at", "rev", "updated_at"])
            per_day[slot] += 1
            moved += 1
    return {"moved": moved, "kept_today": len(stay), "days": days, "per_day": per_day}
