"""
FR-N18: the end-of-timer judgement is read-only and answers from timestamps. The pure rules are tested on facts; the
selector is tested against a real timer row, which must be byte-identical before and after.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from modules.focus import selectors, services
from modules.focus.domain.judgement import EARLY_TOLERANCE, EndState, TimerFacts, judge_timer_end
from modules.focus.models import ActiveTimer
from modules.tracking import services as tracking

START = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
END = START + timedelta(minutes=25)
CID = uuid.uuid4()


def facts(**kw) -> TimerFacts:
    base = {
        "client_id": CID,
        "version": 3,
        "phase": "focus",
        "started_at": START,
        "planned_seconds": 1500,
        "paused_at": None,
        "paused_total_seconds": 0,
        "away_pending": False,
        "overtime_enabled": False,
    }
    return TimerFacts(**{**base, **kw})


def judge(f, *, now=END, version=3, client_id=CID, planned_end=None):
    return judge_timer_end(f, client_id=client_id, expected_version=version, now=now, planned_end=planned_end)


# --- the pure rules ------------------------------------------------------------------------------------------------


def test_no_timer_is_gone():
    assert judge(None).state is EndState.GONE


def test_another_timer_is_changed():
    assert judge(facts(client_id=uuid.uuid4())).state is EndState.CHANGED


@pytest.mark.parametrize("version", [1, 2, 4, 9])
def test_another_version_is_changed(version):
    assert judge(facts(version=version)).state is EndState.CHANGED


def test_the_same_version_but_paused_is_paused():
    assert judge(facts(paused_at=START + timedelta(minutes=10))).state is EndState.PAUSED


def test_the_end_reached_is_ended_with_its_time():
    j = judge(facts())
    assert (j.state, j.phase, j.ends_at, j.overtime, j.away_pending) == (EndState.ENDED, "focus", END, False, False)


def test_a_pause_that_was_resumed_shifts_the_end():
    f = facts(paused_total_seconds=120)
    assert judge(f, now=END).state is EndState.NOT_DUE
    assert judge(f, now=END + timedelta(minutes=2)).ends_at == END + timedelta(minutes=2)


def test_a_clock_a_moment_behind_is_tolerated_but_a_minute_early_is_not_due():
    assert judge(facts(), now=END - EARLY_TOLERANCE).state is EndState.ENDED
    assert judge(facts(), now=END - timedelta(minutes=1)).state is EndState.NOT_DUE


def test_overtime_is_a_live_fact_only_for_a_running_focus_round():
    assert judge(facts(overtime_enabled=True)).overtime is True
    assert judge(facts(overtime_enabled=True, phase="short_break")).overtime is False
    assert judge(facts(overtime_enabled=True, away_pending=True)).overtime is False


def test_a_break_end_is_ended_like_any_other():
    j = judge(facts(phase="short_break", planned_seconds=300), now=START + timedelta(minutes=5))
    assert (j.state, j.phase) == (EndState.ENDED, "short_break")


def test_settled_while_away_is_still_ended_when_the_end_did_not_move():
    away = facts(version=4, away_pending=True)
    j = judge(away, planned_end=END)
    assert (j.state, j.away_pending, j.overtime) == (EndState.ENDED, True, False)


@pytest.mark.parametrize(
    "case",
    [
        dict(version=5, away_pending=True),  # more than the settle's one bump: the student did something
        dict(version=4, away_pending=False),  # a bump that is not the away marker
        dict(version=4, away_pending=True, phase="short_break"),
        dict(version=4, away_pending=True, paused_total_seconds=60),  # the end moved
    ],
)
def test_any_other_version_change_is_changed(case):
    assert judge(facts(**case), planned_end=END).state is EndState.CHANGED


def test_without_the_planned_end_an_away_marker_is_not_recognised():
    assert judge(facts(version=4, away_pending=True)).state is EndState.CHANGED


# --- the selector against a real row --------------------------------------------------------------------------------


@pytest.fixture
def clock(monkeypatch):
    state = {"now": START}
    monkeypatch.setattr(tracking, "_now", lambda: state["now"])
    return state


@pytest.fixture
def running(db, clock):
    user = uuid.uuid4()
    services.update_settings(user, {"overtime_enabled": False})
    timer, _ = services.start(user, client_id=uuid.uuid4())
    return user, timer


def row(user):
    return ActiveTimer.objects.filter(pk=user).values().get()


@pytest.mark.django_db
def test_the_selector_answers_from_the_row_and_the_clock(running):
    user, timer = running

    def ask(now, version=timer.version):
        return selectors.timer_end_judgement(user, timer.client_id, version, now)

    assert ask(END).state is EndState.ENDED
    assert ask(END, version=timer.version + 1).state is EndState.CHANGED
    assert ask(END - timedelta(minutes=2)).state is EndState.NOT_DUE
    assert selectors.timer_end_judgement(user, uuid.uuid4(), timer.version, END).state is EndState.CHANGED
    assert selectors.timer_end_judgement(uuid.uuid4(), timer.client_id, timer.version, END).state is EndState.GONE


@pytest.mark.django_db
def test_asking_leaves_the_timer_row_byte_identical_even_long_after_the_round_ended(running, clock):
    user, timer = running
    before = row(user)
    for now in (START, END - timedelta(minutes=1), END, END + timedelta(hours=3)):
        clock["now"] = now
        selectors.timer_end_judgement(user, timer.client_id, timer.version, now, planned_end=END)
    after = row(user)
    assert after == before  # every column, including `version`, `updated_at`, `last_seen_at` and `away_pending`
    assert after["phase"] == "focus" and after["away_pending"] is False  # nothing was settled


@pytest.mark.django_db
def test_asking_is_one_plain_select_without_a_lock(running):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    user, timer = running
    with CaptureQueriesContext(connection) as ctx:
        selectors.timer_end_judgement(user, timer.client_id, timer.version, END)
    assert len(ctx) == 1
    sql = ctx.captured_queries[0]["sql"].upper()
    assert sql.startswith("SELECT") and "FOR UPDATE" not in sql


@pytest.mark.django_db
def test_a_discarded_timer_is_gone(running):
    user, timer = running
    services.end(user, save=False)
    assert selectors.timer_end_judgement(user, timer.client_id, timer.version, END).state is EndState.GONE


@pytest.mark.django_db
def test_live_end_at_is_none_while_paused_or_away(running):
    user, timer = running
    assert selectors.live_end_at(timer) == END
    timer.paused_at = START + timedelta(minutes=1)
    assert selectors.live_end_at(timer) is None
    timer.paused_at, timer.away_pending = None, True
    assert selectors.live_end_at(timer) is None
