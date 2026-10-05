"""
Derived tables: the daily roll-up (seconds per day and tag combination) and the hour buckets. They are recomputed per
affected day inside the same transaction as every session write (one delete and one insert, so there is no drift), and
can always be rebuilt from `tracking_studysession` (`manage.py rebuild_tracking_rollups`).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta

from django.db import transaction

from .domain import durations
from .models import DailyRollup, HourBucket, StudySession


def session_cells(session: StudySession) -> list[tuple[date, int, int]]:
    paused = max(0, durations.span_seconds(session.started_at, session.ended_at) - session.focus_seconds)
    return durations.split_by_local_hour(session.started_at, session.ended_at, session.tz, paused)


def touched_days(session: StudySession) -> set[date]:
    return {session.study_date} | {d for d, _, _ in session_cells(session)}


def days_for(started_at: datetime, ended_at: datetime, tz: str, focus_seconds: int, study_date: date) -> set[date]:
    paused = max(0, durations.span_seconds(started_at, ended_at) - focus_seconds)
    return {study_date} | {d for d, _, _ in durations.split_by_local_hour(started_at, ended_at, tz, paused)}


@transaction.atomic
def refresh_days(user_id, days: Iterable[date]) -> None:
    for day in sorted(set(days)):
        _refresh_day(user_id, day)


def _refresh_day(user_id, day: date) -> None:
    # A session that starts on the previous day can run past midnight into this one, so both days are read.
    sessions = StudySession.objects.filter(user_id=user_id, study_date__in=[day - timedelta(days=1), day])
    seconds: dict[tuple, int] = defaultdict(int)
    counts: dict[tuple, int] = defaultdict(int)
    hours: Counter[int] = Counter()
    for s in sessions:
        cells = session_cells(s)
        today_seconds = sum(sec for d, _, sec in cells if d == day)
        for d, hour, sec in cells:
            if d == day:
                hours[hour] += sec
        started_today = s.study_date == day
        if today_seconds or started_today:
            key = (s.subject_id, s.chapter_id, s.activity_type, s.source, s.presence_verified)
            seconds[key] += today_seconds
            counts[key] += 1 if started_today else 0
    DailyRollup.objects.filter(user_id=user_id, study_date=day).delete()
    HourBucket.objects.filter(user_id=user_id, study_date=day).delete()
    DailyRollup.objects.bulk_create(
        DailyRollup(
            user_id=user_id,
            study_date=day,
            subject_id=key[0],
            chapter_id=key[1],
            activity_type=key[2],
            source=key[3],
            verified=key[4],
            seconds=sec,
            sessions=counts[key],
        )
        for key, sec in seconds.items()
    )
    HourBucket.objects.bulk_create(
        HourBucket(user_id=user_id, study_date=day, hour=hour, seconds=sec) for hour, sec in hours.items() if sec
    )


def rebuild(user_id, start: date | None = None, end: date | None = None) -> int:
    """Recompute every day that has sessions (or roll-up rows) in the range. Returns how many days were refreshed."""
    sessions = StudySession.objects.filter(user_id=user_id)
    rollups = DailyRollup.objects.filter(user_id=user_id)
    if start:
        sessions, rollups = sessions.filter(study_date__gte=start), rollups.filter(study_date__gte=start)
    if end:
        sessions, rollups = sessions.filter(study_date__lte=end), rollups.filter(study_date__lte=end)
    days = set(sessions.values_list("study_date", flat=True)) | set(rollups.values_list("study_date", flat=True))
    days |= {d + timedelta(days=1) for d in list(days)}  # a midnight crossing lands on the next day too
    refresh_days(user_id, days)
    return len(days)
