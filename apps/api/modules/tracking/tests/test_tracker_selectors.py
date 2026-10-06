"""The reads the tracker alerts rely on: the read-only stopwatch judge, today's goal progress and the streak watch."""

import uuid
from datetime import UTC, date, datetime, time, timedelta

import pytest

from modules.tracking import selectors
from modules.tracking.domain.judgement import RunState
from modules.tracking.models import ActiveStopwatch, DailyRollup, Goal, TrackerSettings

pytestmark = pytest.mark.django_db
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
OTHER = uuid.UUID("7a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d")
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
EVENING = datetime(2026, 10, 5, 17, 5, tzinfo=UTC)  # 22:35 in India on Monday 5 Oct
TODAY = date(2026, 10, 5)
THREE_H = 3 * 3600


def day(n: int) -> date:
    return TODAY - timedelta(days=n)


def studied(user, when: date, minutes: int, tz: str = "Asia/Kolkata"):
    TrackerSettings.objects.get_or_create(pk=user, defaults={"tz": tz})
    DailyRollup.objects.create(
        user_id=user, study_date=when, activity_type="reading", source="manual", seconds=minutes * 60, sessions=1
    )


# --- the read-only judge -------------------------------------------------------------------------------------------


def start_stopwatch(user=USER, **kw):
    return ActiveStopwatch.objects.create(
        user_id=user, started_at=NOW, last_seen_at=NOW, last_active_at=NOW, client_id=uuid.uuid4(), **kw
    )


def test_the_judge_answers_from_the_row_and_never_changes_it():
    sw = start_stopwatch(idle_pending=True, idle_prompted_at=NOW + timedelta(hours=2))
    before = ActiveStopwatch.objects.filter(pk=USER).values().get()
    result = selectors.stopwatch_running_judgement(
        USER, sw.client_id, sw.version, NOW + timedelta(hours=3), after_seconds=THREE_H
    )
    assert result.state is RunState.PAUSED  # the lapsed idle prompt would pause it on the next read ...
    assert ActiveStopwatch.objects.filter(pk=USER).values().get() == before  # ... but asking changes nothing


def test_the_judge_is_per_student():
    mine = start_stopwatch(USER)
    assert (
        selectors.stopwatch_running_judgement(
            OTHER, mine.client_id, mine.version, NOW + timedelta(hours=3), after_seconds=THREE_H
        ).state
        is RunState.GONE
    )


def test_the_judge_sees_a_due_stopwatch():
    sw = start_stopwatch()
    result = selectors.stopwatch_running_judgement(
        USER, sw.client_id, sw.version, NOW + timedelta(hours=3), after_seconds=THREE_H
    )
    assert result.state is RunState.DUE and result.elapsed_seconds == THREE_H


# --- today's progress ----------------------------------------------------------------------------------------------


def test_progress_uses_the_default_goal_until_the_student_sets_one():
    studied(USER, TODAY, 90)
    p = selectors.daily_progress(USER, TODAY)
    assert (p.done_seconds, p.goal_minutes, p.met) == (5400, 120, False)


def test_progress_follows_the_goal_in_force_that_day_and_ignores_other_goals(monkeypatch):
    studied(USER, TODAY, 90)
    Goal.objects.create(user_id=USER, period="daily", subject_key="", target_minutes=60, effective_from=day(3))
    Goal.objects.create(user_id=USER, period="weekly", subject_key="", target_minutes=999, effective_from=day(3))
    p = selectors.daily_progress(USER, TODAY)
    assert (p.goal_minutes, p.met) == (60, True)
    assert selectors.daily_progress(OTHER, TODAY).done_seconds == 0


# --- streaks at risk -----------------------------------------------------------------------------------------------


def at_risk(now=EVENING, local_from=time(16, 0)):
    return selectors.streaks_at_risk(now, local_from=local_from)


def test_a_student_whose_goal_was_met_yesterday_and_not_today_is_at_risk():
    studied(USER, day(1), 130)
    studied(USER, TODAY, 20)
    (risk,) = at_risk()
    assert (risk.user_id, risk.tz, risk.local_date) == (USER, "Asia/Kolkata", TODAY)
    assert (risk.done_seconds, risk.goal_minutes, risk.remaining_seconds) == (1200, 120, 6000)


def test_nothing_studied_today_still_counts_as_at_risk():
    studied(USER, day(1), 130)
    (risk,) = at_risk()
    assert risk.done_seconds == 0 and risk.remaining_seconds == 7200


def test_a_met_goal_today_is_not_at_risk():
    studied(USER, day(1), 130)
    studied(USER, TODAY, 120)
    assert at_risk() == []


def test_without_a_streak_there_is_nothing_to_lose():
    studied(USER, day(1), 119)  # yesterday's goal was missed by a minute
    studied(OTHER, day(2), 300)  # a streak that already ended the day before yesterday
    assert at_risk() == []


def test_the_students_own_goal_decides_yesterday_and_today():
    Goal.objects.create(user_id=USER, period="daily", subject_key="", target_minutes=30, effective_from=day(10))
    studied(USER, day(1), 45)
    studied(USER, TODAY, 20)
    (risk,) = at_risk()
    assert risk.goal_minutes == 30 and risk.remaining_seconds == 600


def test_it_waits_for_the_students_own_local_evening():
    studied(USER, day(1), 130)
    assert at_risk(now=datetime(2026, 10, 5, 9, 0, tzinfo=UTC)) == []  # 14:30 in India
    assert len(at_risk(now=datetime(2026, 10, 5, 10, 30, tzinfo=UTC))) == 1  # 16:00 in India exactly


def test_each_student_is_judged_in_their_own_time_zone():
    studied(USER, day(1), 130)  # India
    studied(OTHER, day(1), 130, tz="America/New_York")  # 13:05 on Monday in New York at EVENING
    assert [r.user_id for r in at_risk()] == [USER]
    new_york_evening = datetime(2026, 10, 5, 22, 0, tzinfo=UTC)  # 18:00 in New York, 03:30 on Tuesday in India
    assert [(r.user_id, r.local_date) for r in at_risk(now=new_york_evening)] == [(OTHER, TODAY)]


def test_it_lists_every_student_at_risk_in_a_few_queries(django_assert_max_num_queries):
    for _ in range(25):
        studied(uuid.uuid4(), day(1), 130)
    with django_assert_max_num_queries(6):
        assert len(at_risk()) == 25


def test_the_streak_length_is_the_existing_selector():
    for n in (1, 2, 3):
        studied(USER, day(n), 130)
    assert selectors.streak(USER, TODAY) == 3
