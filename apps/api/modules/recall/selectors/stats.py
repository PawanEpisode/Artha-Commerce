"""
Report-style reads (FR-F15-71, FR-F15-72, ERD Q-6, Q-13, Q-20): summary, retention, forecast and chapters. Each returns its data and
an `etag` built from the newest `updated_at` among the rows it reads, so the view can answer 304 without recomputing.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from django.db.models import Count, Max, Q

from ..adapters import syllabus as syllabus_adapter
from ..domain import limits as lim
from ..domain.fsrs6 import retrievability
from ..domain.scheduling import forecast as domain_forecast
from ..domain.scheduling import local_date_of, streak
from ..models import RecallCard, RecallDailyRollup, RecallReviewLog
from .study import Study, load_study

RANGES = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}
FORECAST_DAYS = 30


@dataclass(frozen=True)
class Report:
    data: dict
    etag: str


def _etag(*parts) -> str:
    return '"' + hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:24] + '"'


def _days(range_: str) -> int:
    return RANGES.get(range_, 30)


def _newest_rollup(user_id, since: date) -> datetime | None:
    return RecallDailyRollup.objects.filter(user_id=user_id, local_date__gte=since).aggregate(m=Max("updated_at"))["m"]


def _newest_card(user_id) -> datetime | None:
    return RecallCard.objects.filter(user_id=user_id).aggregate(m=Max("updated_at"))["m"]


def stats_summary(user_id, *, range_: str, now: datetime, tz: str | None = None) -> Report:
    study = load_study(user_id, now, tz)
    days = _days(range_)
    since = study.today - timedelta(days=days - 1)
    rows = list(
        RecallDailyRollup.objects.filter(user_id=user_id, local_date__gte=study.today - timedelta(days=400)).order_by(
            "local_date"
        )
    )
    per_day = {r.local_date: r.new_cards + r.learn_reviews + r.review_reviews + r.relearn_reviews for r in rows}
    in_range = [r for r in rows if r.local_date >= since]
    series = [
        {"date": r.local_date.isoformat(), "reviews": per_day[r.local_date], "new": r.new_cards} for r in in_range
    ]
    ratings = {k: sum(getattr(r, k) for r in in_range) for k in ("again", "hard", "good", "easy")}
    total = sum(per_day[r.local_date] for r in in_range)
    seconds = sum(r.seconds for r in in_range)
    longest = best_run(per_day)
    data = {
        "range": range_ if range_ in RANGES else "30d",
        "today": study.today.isoformat(),
        "streak": streak(per_day, study.today),
        "longest_streak": longest,
        "reviews": total,
        "new_cards": sum(r.new_cards for r in in_range),
        "minutes": round(seconds / 60),
        "ratings": ratings,
        "series": series,
        "true_retention": _true_retention(user_id, since, study.today, study),
    }
    return Report(data, _etag("summary", range_, study.tz, _newest_rollup(user_id, since)))


def best_run(per_day: dict[date, int]) -> int:
    best = run = 0
    prev = None
    for d in sorted(per_day):
        if per_day[d] < lim.STREAK_MIN_REVIEWS:
            run, prev = 0, None
            continue
        run = run + 1 if prev is not None and (d - prev).days == 1 else 1
        prev = d
        best = max(best, run)
    return best


def _review_rows(user_id, since: date, today: date):
    undone = RecallReviewLog.objects.filter(user_id=user_id, kind="undo").values("voids_id")
    return RecallReviewLog.objects.filter(
        user_id=user_id,
        kind="review",
        phase_before=2,
        counts_for_scheduling=True,
        local_date__gte=since,
        local_date__lte=today,
    ).exclude(id__in=undone)


def _true_retention(user_id, since: date, today: date, study: Study) -> float | None:
    agg = _review_rows(user_id, since, today).aggregate(n=Count("id"), ok=Count("id", filter=Q(rating__gte=2)))
    return round(agg["ok"] / agg["n"], 4) if agg["n"] else None


def stats_retention(user_id, *, range_: str, now: datetime, tz: str | None = None) -> Report:
    study = load_study(user_id, now, tz)
    since = study.today - timedelta(days=_days(range_) - 1)
    per = (
        _review_rows(user_id, since, study.today)
        .values("local_date")
        .annotate(n=Count("id"), ok=Count("id", filter=Q(rating__gte=2)))
        .order_by("local_date")
    )
    series = [
        {"date": r["local_date"].isoformat(), "reviews": r["n"], "retention": round(r["ok"] / r["n"], 4)} for r in per
    ]
    data = {
        "range": range_ if range_ in RANGES else "30d",
        "target": float(study.settings.desired_retention),
        "overall": _true_retention(user_id, since, study.today, study),
        "series": series,
    }
    return Report(data, _etag("retention", range_, study.tz, _newest_rollup(user_id, since)))


def stats_forecast(user_id, *, now: datetime, days: int = FORECAST_DAYS, tz: str | None = None) -> Report:
    study = load_study(user_id, now, tz)
    days = max(1, min(days, 90))
    due = RecallCard.objects.filter(user_id=user_id, status="active", deleted_at__isnull=True, state__gt=0).values_list(
        "due_at", flat=True
    )
    dates = [local_date_of(d, study.tz, study.day_start_hour) for d in due if d is not None]
    counts = domain_forecast(dates, study.today, days)
    data = {
        "today": study.today.isoformat(),
        "days": [{"date": (study.today + timedelta(days=i)).isoformat(), "due": n} for i, n in enumerate(counts)],
        "overdue": sum(1 for d in dates if d < study.today),
    }
    return Report(data, _etag("forecast", days, study.tz, _newest_card(user_id), _newest_rollup(user_id, study.today)))


@dataclass(frozen=True)
class StrengthRow:
    chapter_id: UUID | None
    cards: int
    due: int
    strength: float | None  # mean predicted retrievability


def recall_strength(
    user_id, chapter_ids: Sequence[UUID | None] | None, *, now: datetime, study: Study | None = None
) -> dict[UUID | None, StrengthRow]:
    """Mean predicted retrievability, active card count and due count per chapter (ERD Q-6; chapter pages and stats)."""
    study = study or load_study(user_id, now)
    qs = RecallCard.objects.filter(user_id=user_id, status="active", deleted_at__isnull=True)
    if chapter_ids is not None:
        qs = qs.filter(chapter_id__in=[c for c in chapter_ids if c is not None])
    acc: dict[UUID | None, list] = {}
    for chapter_id, state, stability, last, due in qs.values_list(
        "chapter_id", "state", "stability", "last_review_at", "due_at"
    ):
        slot = acc.setdefault(chapter_id, [0, 0, 0.0, 0])  # cards, due, sum R, reviewed cards
        slot[0] += 1
        if state > 0 and due is not None and due <= study.day_end:
            slot[1] += 1
        if stability and last:
            elapsed = max(0.0, (now - last).total_seconds() / lim.SECONDS_PER_DAY)
            slot[2] += retrievability(stability, elapsed, study.weights[20])
            slot[3] += 1
    return {c: StrengthRow(c, v[0], v[1], round(v[2] / v[3], 4) if v[3] else None) for c, v in acc.items()}


def stats_chapters(user_id, *, now: datetime, tz: str | None = None) -> Report:
    study = load_study(user_id, now, tz)
    rows = recall_strength(user_id, None, now=now, study=study)
    refs = syllabus_adapter.chapter_refs(rows)
    out = []
    for chapter_id, r in rows.items():
        ref = refs.get(chapter_id)
        out.append(
            {
                "chapter": {"id": str(chapter_id), "key": ref.key, "name": ref.name, "subject_key": ref.subject_key}
                if ref
                else ({"id": str(chapter_id), "key": None, "name": None, "subject_key": None} if chapter_id else None),
                "cards": r.cards,
                "due": r.due,
                "strength": r.strength,
            }
        )
    out.sort(key=lambda r: (r["strength"] is None, r["strength"] if r["strength"] is not None else 1.0, -r["cards"]))
    return Report(
        {"chapters": out}, _etag("chapters", study.tz, _newest_card(user_id), _newest_rollup(user_id, study.today))
    )


@dataclass(frozen=True)
class DueCounts:
    new: int
    learning: int
    due: int


def due_counts(
    user_id, *, now: datetime, subject_key: str | None = None, chapter_ids: Sequence[UUID] | None = None
) -> DueCounts:
    """Counts for chapter pages and F-10: how many cards are new, in learning and due by the end of today."""
    study = load_study(user_id, now)
    qs = RecallCard.objects.filter(user_id=user_id, status="active", deleted_at__isnull=True)
    if subject_key:
        qs = qs.filter(subject_key=subject_key)
    if chapter_ids is not None:
        qs = qs.filter(chapter_id__in=list(chapter_ids))
    agg = qs.aggregate(
        new=Count("id", filter=Q(state=0)),
        learning=Count("id", filter=Q(state__in=(1, 3), due_at__lte=now)),
        due=Count("id", filter=Q(state=2, due_at__lte=study.day_end)),
    )
    return DueCounts(agg["new"], agg["learning"], agg["due"])
