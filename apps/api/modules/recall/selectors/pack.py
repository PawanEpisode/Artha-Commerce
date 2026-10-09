"""
The offline pack (FR-F15-66, ERD Q-8): the cards the device will study, with content, memory state, weights and settings, so the
web can review with its TypeScript scheduler. Up to the plan's pack size, due and next-day learning cards first, then the new-card
allowance. A pure read: `pack_id` and `expires_at` are labels, nothing is stored.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings as django_settings

from core.plans import plan_code_for

from ..domain.quota import FREE
from ..domain.scheduling import Limits, plan_queue
from ..models import RecallQuotaPlan
from .queue import QueueCard, _view, candidates, render_cards
from .study import Study, load_study

PACK_TTL = timedelta(hours=6)


@dataclass(frozen=True)
class Pack:
    pack_id: str
    study: Study
    cards: list[QueueCard]
    expires_at: datetime
    limit: int


def _plan_limit(user_id) -> int:
    row = RecallQuotaPlan.objects.filter(pk=plan_code_for(user_id)).first()
    return row.pack_size if row is not None else FREE.pack_size


def pack_for_device(user_id, *, now: datetime, limit: int | None = None) -> Pack:
    cap = min(_plan_limit(user_id), django_settings.RECALL_PACK_MAX)
    limit = cap if limit is None else max(1, min(limit, cap))
    study = load_study(user_id, now)
    s = study.settings
    # Learning cards due by tomorrow's end go in too, so a student offline overnight still has her next steps
    due, new = candidates(study, learning_ahead=timedelta(days=1))
    views = [_view(r, s.interleave) for r in [*due, *new]]
    real = plan_queue(
        views,
        now,
        Limits(s.new_per_day, s.reviews_per_day, study.new_done, study.reviews_done),
        study.weights[20],
        mode=s.catchup_mode,
        day_end=study.day_end,
    )
    paused = real.catchup.active and s.pause_new_in_catchup
    wide = Limits(0 if paused else s.new_per_day, limit, study.new_done, 0)
    queue = plan_queue(views, now, wide, study.weights[20], mode="off", day_end=study.day_end + timedelta(days=1))
    ids = list(queue.ids)
    ids += [str(r[0]) for r in sorted(due, key=lambda r: (r[6], str(r[0]))) if r[3] in (1, 3) and str(r[0]) not in ids]
    ids = [] if study.vacation else ids[:limit]
    return Pack(uuid.uuid4().hex, study, render_cards(study, ids), now + PACK_TTL, limit)
