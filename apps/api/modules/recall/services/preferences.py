"""Settings and vacation (ERD 3.5). Changing any setting never reschedules a card: due dates move only by a review or an explicit event."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from ..domain import limits as lim
from ..domain.scheduling import local_date_of, study_day_start
from ..errors import InvalidSetting
from ..models import RecallCard, RecallScheduleEvent, RecallSettings
from . import student
from .sessions import valid_tz

VACATION_MAX_DAYS = 60
CATCHUP_MODES = ("auto", "off", "on")


def _issue(field: str, code: str, message: str) -> dict:
    return {"field": field, "code": code, "message": message}


def _int_in(data: dict, field: str, rng: tuple[int, int], errors: list) -> int | None:
    v = data[field]
    if isinstance(v, bool) or not isinstance(v, int) or not rng[0] <= v <= rng[1]:
        errors.append(_issue(field, "out_of_range", f"Use a whole number from {rng[0]} to {rng[1]}."))
        return None
    return v


def _steps(data: dict, field: str, longest: int, errors: list) -> list[int] | None:
    v = data[field]
    ok = (
        isinstance(v, list)
        and len(v) <= longest
        and all(isinstance(x, int) and not isinstance(x, bool) and 1 <= x <= lim.MAX_STEP_MINUTES for x in v)
    )
    if not ok:
        errors.append(_issue(field, "bad_steps", f"At most {longest} steps, each 1 to {lim.MAX_STEP_MINUTES} minutes."))
        return None
    return list(v)


def update_settings(user_id, data: dict, *, now: datetime | None = None) -> RecallSettings:
    now = now or timezone.now()
    errors: list[dict] = []
    changes: dict = {}
    for field, rng in (
        ("new_per_day", lim.NEW_PER_DAY_RANGE),
        ("reviews_per_day", lim.REVIEWS_PER_DAY_RANGE),
        ("max_interval_days", lim.MAX_INTERVAL_RANGE),
        ("day_start_hour", lim.DAY_START_HOUR_RANGE),
        ("leech_threshold", (4, 20)),
        ("quick_minutes_per_day", (5, 240)),
    ):
        if field in data and (v := _int_in(data, field, rng, errors)) is not None:
            changes[field] = v
    if "desired_retention" in data:
        try:
            r = Decimal(str(data["desired_retention"])).quantize(Decimal("0.01"))
            if not Decimal(str(lim.RETENTION_RANGE[0])) <= r <= Decimal(str(lim.RETENTION_RANGE[1])):
                raise ValueError
            changes["desired_retention"] = r
        except (InvalidOperation, ValueError):
            errors.append(_issue("desired_retention", "out_of_range", "Use a value from 0.80 to 0.97."))
    if "learning_steps_min" in data and (v := _steps(data, "learning_steps_min", 4, errors)) is not None:
        changes["learning_steps_min"] = v
    if "relearning_steps_min" in data and (v := _steps(data, "relearning_steps_min", 3, errors)) is not None:
        changes["relearning_steps_min"] = v
    if "tz" in data:
        if isinstance(data["tz"], str) and valid_tz(data["tz"]):
            changes["tz"] = data["tz"]
        else:
            errors.append(_issue("tz", "bad_tz", "Unknown time zone."))
    if "catchup_mode" in data:
        if data["catchup_mode"] in CATCHUP_MODES:
            changes["catchup_mode"] = data["catchup_mode"]
        else:
            errors.append(_issue("catchup_mode", "bad_choice", "Use auto, off or on."))
    for field in (
        "bury_siblings",
        "interleave",
        "pause_new_in_catchup",
        "exam_horizon",
        "recall_counts_as_revision",
        "gestures",
        "show_intervals",
    ):
        if field in data:
            if isinstance(data[field], bool):
                changes[field] = data[field]
            else:
                errors.append(_issue(field, "bad_boolean", "Use true or false."))
    if errors:
        raise InvalidSetting(extra={"errors": errors})
    with transaction.atomic():
        row = RecallSettings.objects.select_for_update().filter(pk=user_id).first() or student.settings_for(user_id)
        if "improve_scheduler_consent" in data:
            consent = bool(data["improve_scheduler_consent"])
            if consent != row.improve_scheduler_consent:
                row.improve_scheduler_consent, row.consent_at = consent, now
        for k, v in changes.items():
            setattr(row, k, v)
        row.save()
    return row


def set_vacation(user_id, until: date | None, *, now: datetime | None = None) -> dict:
    """
    Vacation until a date (at most 60 days ahead): cards due before it wait until the day after, with a `postpone` event
    (reason `vacation`). `None` ends it and lifts the postponements it made. Nothing else is rescheduled.
    """
    now = now or timezone.now()
    with transaction.atomic():
        row = RecallSettings.objects.select_for_update().filter(pk=user_id).first() or student.settings_for(user_id)
        today = local_date_of(now, row.tz, row.day_start_hour)
        if until is not None and not today <= until <= today + timedelta(days=VACATION_MAX_DAYS):
            raise InvalidSetting(
                extra={
                    "errors": [_issue("until", "bad_date", f"Pick a day from today to {VACATION_MAX_DAYS} days ahead.")]
                }
            )
        moved = lifted = 0
        if until is None:
            ids = RecallScheduleEvent.objects.filter(
                user_id=user_id, kind="postpone", reason_code="vacation"
            ).values_list("card_id", flat=True)
            for card in RecallCard.objects.select_for_update(of=("self",)).filter(
                user_id=user_id, id__in=list(ids), postponed_until__gt=now
            ):
                RecallScheduleEvent.objects.create(
                    user_id=user_id,
                    card=card,
                    kind="unpostpone",
                    at=now,
                    from_due=card.due_at,
                    to_due=card.due_scheduled_at,
                    reason_code="vacation",
                )
                card.postponed_until, card.due_at = None, card.due_scheduled_at
                card.rev += 1
                card.save(update_fields=["postponed_until", "due_at", "rev", "updated_at"])
                lifted += 1
        else:
            wake = study_day_start(until + timedelta(days=1), row.tz, row.day_start_hour)
            for card in RecallCard.objects.select_for_update(of=("self",)).filter(
                user_id=user_id, status="active", state__gt=0, due_at__lt=wake
            ):
                RecallScheduleEvent.objects.create(
                    user_id=user_id,
                    card=card,
                    kind="postpone",
                    at=now,
                    from_due=card.due_at,
                    to_due=wake,
                    reason_code="vacation",
                )
                card.postponed_until = wake
                card.due_at = max(card.due_scheduled_at or wake, wake)
                card.rev += 1
                card.save(update_fields=["postponed_until", "due_at", "rev", "updated_at"])
                moved += 1
        row.vacation_until = until
        row.save(update_fields=["vacation_until", "updated_at"])
    return {"vacation_until": until, "postponed": moved, "restored": lifted}
