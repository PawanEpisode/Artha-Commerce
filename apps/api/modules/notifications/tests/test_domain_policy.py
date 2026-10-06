from datetime import UTC, datetime, time, timedelta

from modules.notifications.domain.catalogue import get_event
from modules.notifications.domain.enums import SuppressReason
from modules.notifications.domain.policy import (
    DAILY_CAP,
    EXEMPT_STALE_AFTER,
    Action,
    PolicyInput,
    QuietPreference,
    decide,
)

NOON_IST = datetime(2026, 3, 1, 6, 30, tzinfo=UTC)
NIGHT_IST = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)  # 22:30 local
MORNING_END = datetime(2026, 3, 2, 1, 30, tzinfo=UTC)
QUIET = QuietPreference(True, "Asia/Kolkata", time(22, 0), time(7, 0))


def facts(event="daily_nudge", **kw):
    base = dict(
        spec=get_event(event),
        now=NOON_IST,
        master_on=True,
        channel_enabled=True,
        has_active_device=True,
        quiet=QUIET,
        sent_today=0,
    )
    base.update(kw)
    return PolicyInput(**base)


def test_plain_send():
    assert decide(facts()).action is Action.SEND


def test_rule_order_kill_switch_beats_everything():
    d = decide(facts(event_disabled=True, master_on=False, has_active_device=False))
    assert d.reason is SuppressReason.FLAG_OFF


def test_preference_beats_no_device():
    assert decide(facts(master_on=False, has_active_device=False)).reason is SuppressReason.PREFERENCE
    assert decide(facts(channel_enabled=False)).reason is SuppressReason.PREFERENCE


def test_no_device():
    assert decide(facts(has_active_device=False)).reason is SuppressReason.NO_DEVICE


def test_exempt_events_ignore_quiet_hours_and_cap():
    d = decide(facts("timer_end", now=NIGHT_IST, sent_today=99, intended_at=NIGHT_IST))
    assert d.action is Action.SEND


def test_exempt_event_that_is_late_is_dropped():
    late = NIGHT_IST - EXEMPT_STALE_AFTER - timedelta(seconds=1)
    assert decide(facts("timer_end", now=NIGHT_IST, intended_at=late)).reason is SuppressReason.STALE
    just_in_time = NIGHT_IST - EXEMPT_STALE_AFTER
    assert decide(facts("timer_end", now=NIGHT_IST, intended_at=just_in_time)).action is Action.SEND


def test_expired_event_is_stale_before_quiet_hours_are_considered():
    d = decide(facts(now=NIGHT_IST, expires_at=NIGHT_IST - timedelta(minutes=1)))
    assert d.reason is SuppressReason.STALE


def test_quiet_hours_defer_to_window_end():
    d = decide(facts(now=NIGHT_IST))
    assert d.action is Action.DEFER and d.deliver_at == MORNING_END


def test_quiet_hours_suppress_when_it_would_expire_first():
    d = decide(facts("streak_at_risk", now=NIGHT_IST, expires_at=NIGHT_IST + timedelta(hours=3)))
    assert d.reason is SuppressReason.QUIET_HOURS


def test_quiet_hours_disabled_sends():
    off = QuietPreference(False, "Asia/Kolkata", time(22, 0), time(7, 0))
    assert decide(facts(now=NIGHT_IST, quiet=off)).action is Action.SEND
    assert decide(facts(now=NIGHT_IST, quiet=None)).action is Action.SEND


def test_cap_for_low_priority_and_one_extra_for_priority_one():
    assert decide(facts(sent_today=DAILY_CAP)).reason is SuppressReason.CAP
    assert decide(facts("goal_reached", sent_today=DAILY_CAP)).action is Action.SEND
    assert decide(facts("goal_reached", sent_today=DAILY_CAP + 1)).reason is SuppressReason.CAP
    assert decide(facts("revision_due", sent_today=DAILY_CAP)).reason is SuppressReason.CAP  # priority 2: no extra
