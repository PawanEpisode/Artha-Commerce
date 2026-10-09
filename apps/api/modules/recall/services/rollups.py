"""
Daily and per-chapter counters (ERD 3.5). Derived and rebuildable from the review log:

- incremented only when a log row was newly inserted (a duplicate event counts nothing),
- an undo applies the negative of the voided row, on the voided row's own study day,
- a replay that changes the phase a review was in moves one count between the `new`/`learn`/`review`/`relearn` columns.

Every write is an upsert on the row's key: a conditional UPDATE first, a create inside a savepoint when the row does not exist
yet, and an UPDATE again when another request created it in between. Never read-then-write.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import F

from ..models import RecallCard, RecallChapterRollup, RecallDailyRollup, RecallReviewLog

PHASE_COLUMN = {0: "new_cards", 1: "learn_reviews", 2: "review_reviews", 3: "relearn_reviews"}
RATING_COLUMN = {1: "again", 2: "hard", 3: "good", 4: "easy"}
MANDATORY = 2


def daily_deltas(
    *, phase_before: int | None, rating: int | None, importance: int, duration_ms: int | None, sign: int = 1
) -> dict:
    out: dict[str, int] = defaultdict(int)
    if phase_before is not None:
        out[PHASE_COLUMN.get(phase_before, "review_reviews")] += sign
    if rating in RATING_COLUMN:
        out[RATING_COLUMN[rating]] += sign
    if importance == MANDATORY:
        out["mandatory_reviews"] += sign
    out["seconds"] += sign * ((duration_ms or 0) // 1000)
    return dict(out)


def chapter_deltas(*, rating: int | None, importance: int, sign: int = 1) -> dict:
    out = {"reviews": sign}
    if rating == 1:
        out["again"] = sign
    if importance == MANDATORY:
        out["mandatory_reviews"] = sign
    return out


def _bump(model, key: dict, deltas: Mapping[str, int]) -> None:
    if not deltas or not any(deltas.values()):
        return
    updates = {name: F(name) + amount for name, amount in deltas.items() if amount}
    if model.objects.filter(**key).update(**updates):
        return
    try:
        with transaction.atomic():
            model.objects.create(**key, **deltas)
    except IntegrityError:
        model.objects.filter(**key).update(**updates)


def bump_daily(user_id, local_date: date, deltas: Mapping[str, int]) -> None:
    _bump(RecallDailyRollup, {"user_id": user_id, "local_date": local_date}, deltas)


def bump_chapter(user_id, local_date: date, chapter_id, deltas: Mapping[str, int]) -> None:
    _bump(RecallChapterRollup, {"user_id": user_id, "local_date": local_date, "chapter_id": chapter_id}, deltas)


def apply_row(user_id, *, local_date, chapter_id, phase_before, rating, importance, duration_ms, sign=1) -> None:
    bump_daily(
        user_id,
        local_date,
        daily_deltas(
            phase_before=phase_before, rating=rating, importance=importance, duration_ms=duration_ms, sign=sign
        ),
    )
    bump_chapter(user_id, local_date, chapter_id, chapter_deltas(rating=rating, importance=importance, sign=sign))


def rebuild(user_id, since: date | None = None) -> int:
    """Recompute the counters from the log (non-voided review rows) and replace them. Returns the number of rows read."""
    log = RecallReviewLog.objects.filter(user_id=user_id, kind="review")
    voided = set(RecallReviewLog.objects.filter(user_id=user_id, kind="undo").values_list("voids_id", flat=True))
    if since is not None:
        log = log.filter(local_date__gte=since)
    cards = {c["id"]: c for c in RecallCard.objects.filter(user_id=user_id).values("id", "importance", "chapter_id")}
    daily: dict[date, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    chapter: dict[tuple[date, object], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    count = 0
    for row in log.iterator():
        count += 1
        if row.id in voided:
            continue
        card = cards.get(row.card_id, {})
        importance = card.get("importance", 0)
        for name, amount in daily_deltas(
            phase_before=row.phase_before, rating=row.rating, importance=importance, duration_ms=row.duration_ms
        ).items():
            daily[row.local_date][name] += amount
        for name, amount in chapter_deltas(rating=row.rating, importance=importance).items():
            chapter[(row.local_date, card.get("chapter_id"))][name] += amount
    with transaction.atomic():
        d_qs = RecallDailyRollup.objects.filter(user_id=user_id)
        c_qs = RecallChapterRollup.objects.filter(user_id=user_id)
        if since is not None:
            d_qs, c_qs = d_qs.filter(local_date__gte=since), c_qs.filter(local_date__gte=since)
        d_qs.delete()
        c_qs.delete()
        RecallDailyRollup.objects.bulk_create(
            [RecallDailyRollup(user_id=user_id, local_date=day, **vals) for day, vals in daily.items()]
        )
        RecallChapterRollup.objects.bulk_create(
            [
                RecallChapterRollup(user_id=user_id, local_date=day, chapter_id=chap, **vals)
                for (day, chap), vals in chapter.items()
            ]
        )
    return count
