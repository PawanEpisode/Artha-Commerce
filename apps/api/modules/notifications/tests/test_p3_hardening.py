"""
Phase 3 hardening (X-01.1 W3.7, gate G3): every phase 3 push respects quiet hours and the kill switches, and no student
gets more than the daily cap (3, plus one reserved slot for priority 1) of counted pushes in one local day. The last
test runs the exact check from docs/X-01-ROLLOUT.md (W3.7) on PostgreSQL.
"""

import itertools
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta

import pytest
from django.db import connection

from modules.notifications.domain.catalogue import EVENTS
from modules.notifications.domain.copy import _BUILDERS
from modules.notifications.domain.policy import DAILY_CAP, PRIORITY_ONE_EXTRA
from modules.notifications.domain.quiet_hours import local_date
from modules.notifications.models import Delivery
from modules.notifications.services import notify as notify_service
from modules.notifications.tests.helpers import register

pytestmark = pytest.mark.django_db
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
NIGHT = datetime(2026, 10, 7, 17, 30, tzinfo=UTC)  # 23:00 in India, inside the default quiet hours
MORNING = datetime(2026, 10, 7, 3, 0, tzinfo=UTC)  # 08:30 in India


def _context(event: str) -> tuple[dict, dict]:
    """Words for one alert of `event` and a dedupe reference that is new each call."""
    ref = uuid.uuid4().hex[:10]
    return {
        "stopwatch_long": ({"client_id": ref, "minutes": 190}, {"client_id": ref}),
        "goal_reached": ({"studied_minutes": 120, "local_date": ref}, {"local_date": ref}),
        "streak_at_risk": ({"streak_days": 3, "remaining_minutes": 30, "local_date": ref}, {"local_date": ref}),
        "daily_nudge": ({"message": "Keep going.", "local_date": ref}, {"local_date": ref}),
        "revision_due": ({"due_count": 2, "local_date": ref}, {"local_date": ref}),
        "exam_milestone": ({"days_left": 7}, {"days_left": ref}),
        "content_published": ({"title": "A paper", "item_id": ref}, {"item_id": ref}),
        "daily_digest": ({"unread": 1, "local_date": ref}, {"local_date": ref}),
    }[event]


#: Every non-exempt event that can be pushed and has words: the phase 3 alerts.
P3_PUSH_EVENTS = sorted(
    key
    for key, spec in EVENTS.items()
    if not spec.exempt and key in _BUILDERS and key != "weekly_summary"  # the weekly summary is email only
)


def test_the_list_covers_the_phase_3_alerts():
    assert set(P3_PUSH_EVENTS) >= {
        "stopwatch_long",
        "goal_reached",
        "streak_at_risk",
        "daily_nudge",
        "revision_due",
        "exam_milestone",
        "content_published",
        "daily_digest",
    }


@pytest.fixture(autouse=True)
def device():
    return register(USER, platform="android", browser="chrome").device


def notify(event, now):
    context, ref = _context(event)
    return notify_service.notify(USER, event, context=context, dedupe_ref=ref, now=now).dispatch


@pytest.mark.parametrize("event", P3_PUSH_EVENTS)
def test_every_phase_3_push_waits_for_the_end_of_quiet_hours(event, fake_push):
    result = notify(event, NIGHT)
    assert result.outcome in ("deferred", "suppressed") and fake_push.sent == []


@pytest.mark.parametrize("event", P3_PUSH_EVENTS)
def test_every_phase_3_push_obeys_its_kill_switch(event, fake_push, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = [event]
    result = notify(event, MORNING + timedelta(hours=2))
    assert result.outcome == "suppressed" and result.reason.value == "flag_off" and fake_push.sent == []


@pytest.mark.parametrize("event", P3_PUSH_EVENTS)
def test_every_phase_3_push_obeys_the_sending_flag(event, fake_push, monkeypatch):
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    assert notify(event, MORNING + timedelta(hours=2)).outcome == "suppressed" and fake_push.sent == []


def test_a_busy_day_never_goes_past_the_cap(fake_push):
    """Twenty alerts of every priority over one local day: at most 3 counted, plus one for priority 1."""
    events = itertools.cycle(P3_PUSH_EVENTS)
    start = MORNING + timedelta(hours=1)  # 09:30 in India
    for i in range(20):
        notify(next(events), start + timedelta(minutes=30 * i))
    counted = Delivery.objects.filter(user_id=USER, status="sent", counts_toward_cap=True)
    per_day = Counter(local_date(d.attempted_at, "Asia/Kolkata") for d in counted)
    assert per_day and max(per_day.values()) <= DAILY_CAP + PRIORITY_ONE_EXTRA
    priority_two_or_three = counted.filter(notification__priority__gte=2)
    assert max(Counter(local_date(d.attempted_at, "Asia/Kolkata") for d in priority_two_or_three).values()) <= DAILY_CAP


@pytest.mark.skipif(connection.vendor != "postgresql", reason="The rollout check is PostgreSQL SQL (CI runs it)")
def test_the_rollout_cap_check_returns_no_rows(fake_push):
    events = itertools.cycle(P3_PUSH_EVENTS)
    for i in range(20):
        notify(next(events), MORNING + timedelta(hours=1, minutes=30 * i))
    with connection.cursor() as cursor:
        cursor.execute(
            """
            select user_id, date_trunc('day', attempted_at at time zone 'Asia/Kolkata') as day, count(*)
            from notifications_delivery
            where status = 'sent' and counts_toward_cap and attempted_at > %s - interval '7 days'
            group by 1, 2 having count(*) > 4
            """,
            [MORNING + timedelta(days=1)],
        )
        assert cursor.fetchall() == []
