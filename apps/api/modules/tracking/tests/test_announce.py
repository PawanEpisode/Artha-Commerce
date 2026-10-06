"""
FR-N19 for `tracking`: every public service action that can move the stopwatch emits exactly one `stopwatch_changed`, and
every one that can raise today's counted time emits `goal_reached` at most once, when the daily goal goes from not met to
met. An action that changes nothing, or is rolled back, announces nothing. `tracking` knows nothing about who listens.
"""

import inspect
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from core import events
from modules.tracking import events as tracking_events
from modules.tracking import services
from modules.tracking.errors import ConflictError
from modules.tracking.models import ActiveStopwatch

pytestmark = pytest.mark.django_db
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
OTHER = uuid.UUID("7a1d2c3b-4e5f-4a6b-8c7d-9e0f1a2b3c4d")
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)  # 10:00 on Monday 5 Oct in India


class World:
    """One student, a movable clock, and a recorder on the event bus."""

    def __init__(self, monkeypatch, capture):
        self.now, self.capture = NOW, capture
        self.stopwatch_events, self.goal_events = [], []
        monkeypatch.setattr(services, "_now", lambda: self.now)
        events.subscribe(tracking_events.STOPWATCH_CHANGED, self.on_stopwatch)
        events.subscribe(tracking_events.GOAL_REACHED, self.on_goal)

    def on_stopwatch(self, **payload):
        self.stopwatch_events.append(payload)

    def on_goal(self, **payload):
        self.goal_events.append(payload)

    def close(self):
        events._subscribers[tracking_events.STOPWATCH_CHANGED].remove(self.on_stopwatch)
        events._subscribers[tracking_events.GOAL_REACHED].remove(self.on_goal)

    def run(self, fn, *args, user=USER, **kwargs):
        """Runs a service action the way a request does: the after-commit hooks fire when it finishes."""
        with self.capture(execute=True):
            return fn(user, *args, **kwargs)

    def go(self, **delta):
        self.now += timedelta(**delta)

    def start(self, user=USER):
        return self.run(services.start_stopwatch, client_id=uuid.uuid4(), user=user)[0]

    def study(self, minutes, *, user=USER, ended_ago=timedelta(0)):
        end = self.now - ended_ago
        return self.run(
            services.add_manual,
            client_id=uuid.uuid4(),
            started_at=end - timedelta(minutes=minutes),
            ended_at=end,
            user=user,
        )

    def clear(self):
        self.stopwatch_events.clear()
        self.goal_events.clear()

    @property
    def sw(self):
        return ActiveStopwatch.objects.get(pk=USER)


@pytest.fixture
def w(monkeypatch, django_capture_on_commit_callbacks):
    world = World(monkeypatch, django_capture_on_commit_callbacks)
    yield world
    world.close()


def prepare_nothing(w):
    pass


def prepare_running(w):
    w.start()
    w.go(minutes=10)


def prepare_paused(w):
    prepare_running(w)
    w.run(services.pause_stopwatch)


def prepare_idle_prompted(w):
    prepare_running(w)
    w.run(services.answer_idle, answer="prompted")


# (id, prepare, act, expected `stopwatch_changed` count)
STOPWATCH_CASES = [
    ("start", prepare_nothing, lambda w: w.start(), 1),
    ("start_retried", prepare_running, lambda w: w.run(services.start_stopwatch, client_id=w.sw.client_id), 0),
    ("pause", prepare_running, lambda w: w.run(services.pause_stopwatch), 1),
    ("pause_when_paused", prepare_paused, lambda w: w.run(services.pause_stopwatch), 0),
    ("resume", prepare_paused, lambda w: w.run(services.resume_stopwatch), 1),
    ("resume_when_running", prepare_running, lambda w: w.run(services.resume_stopwatch), 0),
    (
        "change_context",
        prepare_running,
        lambda w: w.run(services.change_stopwatch_context, version=w.sw.version, changes={"activity_type": "practice"}),
        1,
    ),
    ("poll", prepare_running, lambda w: w.run(services.sync_stopwatch), 0),
    ("heartbeat", prepare_running, lambda w: w.run(services.sync_stopwatch, alive=True), 0),
    ("activity", prepare_running, lambda w: w.run(services.sync_stopwatch, active=True), 0),
    ("sync_without_stopwatch", prepare_nothing, lambda w: w.run(services.sync_stopwatch), 0),
    ("idle_prompt_shown", prepare_running, lambda w: w.run(services.answer_idle, answer="prompted"), 0),
    ("idle_prompt_answered", prepare_idle_prompted, lambda w: w.run(services.answer_idle, answer="still_studying"), 0),
    (
        "idle_prompt_lapses_on_the_next_read",
        lambda w: (prepare_idle_prompted(w), w.go(minutes=3)),
        lambda w: w.run(services.sync_stopwatch),
        1,
    ),
    ("stop_saved", prepare_running, lambda w: w.run(services.stop_stopwatch), 1),
    ("stop_discarded", prepare_running, lambda w: w.run(services.stop_stopwatch, save=False), 1),
    ("stop_too_short", lambda w: w.start(), lambda w: w.run(services.stop_stopwatch), 1),
    ("erase_with_stopwatch", prepare_running, lambda w: w.run(services.delete_all_for_user), 1),
    ("erase_without_stopwatch", prepare_nothing, lambda w: w.run(services.delete_all_for_user), 0),
]


@pytest.mark.parametrize("name, prepare, act, expected", STOPWATCH_CASES, ids=[c[0] for c in STOPWATCH_CASES])
def test_every_service_action_announces_exactly_once_when_it_moves_the_stopwatch(w, name, prepare, act, expected):
    prepare(w)
    w.clear()
    act(w)
    assert len(w.stopwatch_events) == expected, w.stopwatch_events
    for payload in w.stopwatch_events:
        assert payload["user_id"] == str(USER) and payload["at"] == w.now


def test_a_refused_action_rolls_back_and_announces_nothing(w):
    w.start()
    w.clear()
    with pytest.raises(ConflictError):
        w.run(services.pause_stopwatch, version=w.sw.version + 7)  # stale version
    with pytest.raises(ConflictError):
        w.run(services.start_stopwatch, client_id=uuid.uuid4())  # another stopwatch is running
    assert w.stopwatch_events == []


def test_the_announcement_comes_after_the_commit_not_before(w, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        services.start_stopwatch(USER, client_id=uuid.uuid4())
    assert w.stopwatch_events == [] and len(callbacks) == 1  # held until the transaction commits
    callbacks[0]()
    assert len(w.stopwatch_events) == 1


def test_a_running_stopwatch_payload_carries_what_a_consumer_needs_to_plan_its_mark(w):
    sw = w.start()
    w.go(minutes=10)
    w.run(services.pause_stopwatch)
    w.go(minutes=5)
    w.run(services.resume_stopwatch)
    p = w.stopwatch_events[-1]
    assert p == {
        "user_id": str(USER),
        "active": True,
        "client_id": str(sw.client_id),
        "version": w.sw.version,
        "started_at": NOW,
        "paused": False,
        "paused_total_seconds": 300,
        "at": w.now,
    }


def test_a_stopped_stopwatch_announces_only_that_it_is_gone(w):
    w.start()
    w.go(minutes=5)
    w.run(services.stop_stopwatch)
    assert w.stopwatch_events[-1] == {"user_id": str(USER), "active": False, "at": w.now}


# --- the daily goal ------------------------------------------------------------------------------------------------


def test_reaching_the_default_goal_announces_once(w):
    w.study(100)
    assert w.goal_events == []
    w.study(25, ended_ago=timedelta(minutes=110))  # 125 minutes today against the default 120
    (p,) = w.goal_events
    assert p == {
        "user_id": str(USER),
        "local_date": "2026-10-05",
        "done_seconds": 125 * 60,
        "goal_minutes": 120,
        "at": w.now,
    }


def test_time_after_the_goal_is_met_announces_nothing_more(w):
    w.study(130)
    w.study(30, ended_ago=timedelta(hours=3))
    assert len(w.goal_events) == 1


def test_a_single_long_session_can_reach_the_goal_by_itself(w):
    w.study(180)
    assert len(w.goal_events) == 1


def test_the_students_own_goal_is_the_one_that_counts(w):
    services.set_goals(USER, [{"period": "daily", "target_minutes": 45, "subject_id": None}])
    w.study(30)
    assert w.goal_events == []
    w.study(20, ended_ago=timedelta(hours=2))
    assert len(w.goal_events) == 1 and w.goal_events[0]["goal_minutes"] == 45


def test_a_goal_per_subject_or_per_week_is_not_the_daily_goal(w):
    services.set_goals(USER, [{"period": "weekly", "target_minutes": 30, "subject_id": None}])
    w.study(60)
    assert w.goal_events == []  # the weekly goal is met, the (default) daily goal of 120 minutes is not


def test_time_on_another_day_does_not_count_towards_today(w):
    w.study(200, ended_ago=timedelta(days=1))
    assert w.goal_events == []


def test_the_stopwatch_reaching_the_goal_announces_both_events_once_each(w):
    services.set_goals(USER, [{"period": "daily", "target_minutes": 15, "subject_id": None}])
    w.start()
    w.go(minutes=20)
    w.clear()
    w.run(services.stop_stopwatch)
    assert len(w.goal_events) == 1 and len(w.stopwatch_events) == 1


def test_deleting_a_session_never_announces_a_goal(w):
    session, _ = w.study(60)
    w.clear()
    w.run(services.delete_session, session.id)
    assert w.goal_events == []


def test_undoing_a_delete_that_restores_the_goal_announces_it(w):
    session, _ = w.study(130)
    w.clear()
    audit = w.run(services.delete_session, session.id)
    w.run(services.undo, str(audit.id))
    assert len(w.goal_events) == 1


def test_editing_a_session_longer_can_reach_the_goal(w):
    session, _ = w.study(60)
    w.clear()
    w.run(
        services.edit_session,
        session.id,
        {"started_at": session.started_at - timedelta(hours=2), "ended_at": session.ended_at},
    )
    assert len(w.goal_events) == 1


def test_a_replayed_manual_entry_announces_nothing(w):
    cid = uuid.uuid4()
    end = w.now
    w.run(services.add_manual, client_id=cid, started_at=end - timedelta(hours=3), ended_at=end)
    assert len(w.goal_events) == 1
    w.clear()
    w.run(services.add_manual, client_id=cid, started_at=end - timedelta(hours=3), ended_at=end)
    assert w.goal_events == []


def test_a_rolled_back_session_announces_nothing(w):
    w.study(60)
    w.clear()
    with pytest.raises(ConflictError):
        w.study(90, ended_ago=timedelta(minutes=30))  # overlaps the first: refused, nothing written
    assert w.goal_events == []


def test_the_goal_announcement_comes_after_the_commit(w, django_capture_on_commit_callbacks):
    end = w.now
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        services.add_manual(USER, client_id=uuid.uuid4(), started_at=end - timedelta(hours=3), ended_at=end)
    assert w.goal_events == [] and len(callbacks) >= 1
    for callback in callbacks:
        callback()
    assert len(w.goal_events) == 1


def test_one_students_time_never_announces_another_students_goal(w):
    w.study(200, user=OTHER)
    assert [p["user_id"] for p in w.goal_events] == [str(OTHER)]
    w.clear()
    w.study(10)
    assert w.goal_events == []


def test_the_students_own_time_zone_decides_which_day_it_is(w):
    # 20:30 UTC on Monday is 02:00 on Tuesday in India but still Monday evening in New York.
    services.update_settings(USER, {"tz": "America/New_York"})
    w.now = datetime(2026, 10, 5, 20, 30, tzinfo=UTC)
    w.study(180)
    assert [p["local_date"] for p in w.goal_events] == ["2026-10-05"]


# --- the guard -----------------------------------------------------------------------------------------------------


def _public():
    return {
        name
        for name, fn in inspect.getmembers(services, inspect.isfunction)
        if not name.startswith("_") and fn.__module__ == services.__name__
    }


def test_no_public_action_can_be_added_without_announcing_or_being_listed_here():
    """
    Guard for the next person who adds an action to `services`: announce it, or say why it cannot move the stopwatch
    (or raise today's counted time).
    """
    not_stopwatch = {
        "get_or_create_settings",
        "get_timezone",
        "update_settings",
        "reset_settings",
        "register_live_timer_provider",
        "live_timer_kind",
        "assert_no_live_timer",
        "record_session",
        "add_manual",
        "add_auto",
        "delete_session",
        "undo",
        "edit_session",
        "merge_sessions",
        "split_session",
        "set_goals",
        "local_today",
        "reconcile_coverage",
    }
    announcing = {n for n in _public() if getattr(getattr(services, n), "announces_stopwatch_changes", False)}
    assert _public() - announcing == not_stopwatch


def test_every_action_that_can_raise_todays_time_announces_the_goal_or_calls_one_that_does():
    announcing = {n for n in _public() if getattr(getattr(services, n), "announces_goal_reached", False)}
    # `add_manual` and `add_auto` write through `record_session`; `delete_session` and `split_session` cannot raise the
    # total; `set_goals` changes the target, not the time, and a goal lowered on purpose is not "reached"; the stopwatch
    # saves through `record_session`.
    assert announcing == {"record_session", "edit_session", "undo", "merge_sessions"}
