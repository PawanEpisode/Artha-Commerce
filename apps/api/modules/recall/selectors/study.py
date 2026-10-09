"""
What every read of the study day needs, loaded once: the student's settings (a default row in memory when she has none, so a GET
never writes), the scheduler configuration and weights, her study clock and today's counters. Pure reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..domain.fsrs6 import DEFAULT_WEIGHTS, Cfg
from ..domain.scheduling import end_of_study_day, local_date_of
from ..errors import InvalidSetting
from ..models import RecallDailyRollup, RecallParams, RecallSettings


def get_settings(user_id) -> RecallSettings:
    """Her settings row, or an unsaved row of defaults. Never creates one."""
    return RecallSettings.objects.select_related("params").filter(pk=user_id).first() or RecallSettings(user_id=user_id)


def active_params(settings: RecallSettings) -> tuple[tuple[float, ...], object, str]:
    """`(weights, params id, scheduler version)`: her own set when she has one, else the seeded default."""
    row = settings.params if settings.params_id else None
    row = row or RecallParams.objects.filter(scope="default", status="active").first()
    if row is None:
        return DEFAULT_WEIGHTS, None, "fsrs-6.0"
    return tuple(float(x) for x in row.weights), row.id, row.scheduler_version


def valid_tz(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return False
    return True


@dataclass(frozen=True)
class Study:
    user_id: object
    now: datetime
    settings: RecallSettings
    cfg: Cfg
    weights: tuple[float, ...]
    params_id: object
    scheduler_version: str
    tz: str
    day_start_hour: int
    today: date
    day_end: datetime  # the first instant of the next study day
    new_done: int
    reviews_done: int  # reviews of graduated cards (review and relearning phases); the daily maximum counts these

    @property
    def vacation(self) -> bool:
        until = self.settings.vacation_until
        return until is not None and self.today <= until


def load_study(user_id, now: datetime, tz: str | None = None) -> Study:
    s = get_settings(user_id)
    if tz is not None and not valid_tz(tz):
        raise InvalidSetting(extra={"errors": [{"field": "tz", "code": "bad_tz", "message": "Unknown time zone."}]})
    tz = tz or s.tz
    weights, params_id, version = active_params(s)
    retention = s.desired_retention if isinstance(s.desired_retention, Decimal) else Decimal(str(s.desired_retention))
    cfg = Cfg(
        desired_retention=float(retention),
        learning_steps=tuple(int(x) for x in s.learning_steps_min),
        relearning_steps=tuple(int(x) for x in s.relearning_steps_min),
        max_interval_days=int(s.max_interval_days),
        fuzz=True,
    )
    today = local_date_of(now, tz, s.day_start_hour)
    row = RecallDailyRollup.objects.filter(user_id=user_id, local_date=today).first()
    return Study(
        user_id,
        now,
        s,
        cfg,
        weights,
        params_id,
        version,
        tz,
        s.day_start_hour,
        today,
        end_of_study_day(now, tz, s.day_start_hour),
        row.new_cards if row else 0,
        (row.review_reviews + row.relearn_reviews) if row else 0,
    )


def recent_seconds_per_review(user_id, today: date, days: int = 14, default: float = 20.0) -> float:
    rows = RecallDailyRollup.objects.filter(user_id=user_id, local_date__gte=today - timedelta(days=days)).values_list(
        "seconds", "new_cards", "learn_reviews", "review_reviews", "relearn_reviews"
    )
    seconds = reviews = 0
    for sec, *counts in rows:
        seconds += sec
        reviews += sum(counts)
    return seconds / reviews if reviews >= 20 and seconds else default
