"""
FR-N19: every public service action that can move the timer emits exactly one `timer_changed` after commit, and an
action that changes nothing (or is rolled back) emits none. `focus` knows nothing about who listens.
"""

import inspect
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from core import events
from modules.focus import events as focus_events
from modules.focus import services
from modules.focus.errors import ConflictError
from modules.focus.models import ActiveTimer
from modules.tracking import services as tracking

pytestmark = pytest.mark.django_db
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)


class World:
    """One student, a movable clock, and a recorder on the event bus."""

    def __init__(self, monkeypatch, capture):
        self.now, self.capture, self.events = NOW, capture, []
        monkeypatch.setattr(tracking, "_now", lambda: self.now)
        events.subscribe(focus_events.TIMER_CHANGED, self.record)

    def record(self, **payload):
        self.events.append(payload)

    def close(self):
        events._subscribers[focus_events.TIMER_CHANGED].remove(self.record)

    def run(self, fn, *args, **kwargs):
        """Runs a service action the way a request does: the after-commit hooks fire when it finishes."""
        with self.capture(execute=True):
            return fn(USER, *args, **kwargs)

    def start(self, overtime=False, **kw):
        services.update_settings(USER, {"overtime_enabled": overtime})
        return self.run(services.start, client_id=kw.pop("client_id", uuid.uuid4()), **kw)[0]

    def go(self, **delta):
        self.now += timedelta(**delta)

    @property
    def timer(self):
        return ActiveTimer.objects.get(pk=USER)


@pytest.fixture
def w(monkeypatch, django_capture_on_commit_callbacks):
    world = World(monkeypatch, django_capture_on_commit_callbacks)
    yield world
    world.close()


def at_end(w, **kw):
    w.start(**kw)
    w.go(minutes=25)


# (id, prepare, act, expected events). `prepare` runs before the recorder is emptied; `act` is the one action.
def prepare_nothing(w):
    pass


def prepare_running(w):
    w.start()
    w.go(minutes=10)


def prepare_paused(w):
    prepare_running(w)
    w.run(services.pause)


def prepare_break(w):
    w.start()
    w.go(minutes=25)
    w.run(services.complete)  # the short break begins by itself


def prepare_away(w):
    w.start()
    w.go(minutes=26)
    w.run(services.sync)  # no heartbeat: the round settles as away_pending


def prepare_overtime(w):
    w.start(overtime=True)
    for _ in range(14):  # the tab stays open (a heartbeat every 2 minutes) well past the 25 minute target
        w.go(minutes=2)
        w.run(services.sync, alive=True)


def prepare_at_target(w):
    w.start(overtime=True)
    w.go(minutes=25, seconds=30)  # the alert has just arrived; the round runs on in overtime


def tap(w, action, **kw):
    """A button on the timer alert (X-01.1 W3.6), for the phase that is live now unless told otherwise."""
    timer = w.timer
    kw = {"client_id": timer.client_id, "version": timer.version, "issued_at": w.now, **kw}
    return w.run(services.act_from_notification, action=action, **kw)


CASES = [
    ("start", prepare_nothing, lambda w: w.start(), 1),
    ("start_retried", prepare_running, lambda w: w.run(services.start, client_id=w.timer.client_id), 0),
    ("pause", prepare_running, lambda w: w.run(services.pause), 1),
    ("pause_when_paused", prepare_paused, lambda w: w.run(services.pause), 0),
    ("resume", prepare_paused, lambda w: w.run(services.resume), 1),
    ("resume_when_running", prepare_running, lambda w: w.run(services.resume), 0),
    ("extend", prepare_running, lambda w: w.run(services.extend), 1),
    ("complete_at_zero", lambda w: (w.start(), w.go(minutes=25)), lambda w: w.run(services.complete), 1),
    ("complete_in_overtime", prepare_overtime, lambda w: w.run(services.complete), 0),
    ("skip_break", prepare_break, lambda w: w.run(services.skip_break), 1),
    ("end_early_saved", prepare_running, lambda w: w.run(services.end, save=True), 1),
    ("end_discarded", prepare_running, lambda w: w.run(services.end, save=False), 1),
    ("end_overtime_completes", prepare_overtime, lambda w: w.run(services.end), 1),
    ("claim_count", prepare_away, lambda w: w.run(services.claim, count=True), 1),
    ("claim_discard", prepare_away, lambda w: w.run(services.claim, count=False), 1),
    ("claim_nothing_to_answer", prepare_running, lambda w: w.run(services.claim, count=True), 0),
    (
        "change_context",
        prepare_running,
        lambda w: w.run(services.change_context, version=w.timer.version, changes={"activity_type": "practice"}),
        1,
    ),
    ("heartbeat", prepare_running, lambda w: w.run(services.sync, alive=True), 0),
    ("poll", prepare_running, lambda w: w.run(services.sync), 0),
    (
        "settle_into_break",
        lambda w: (w.start(), w.go(minutes=25, seconds=1)),
        lambda w: w.run(services.sync, alive=True),
        1,
    ),
    ("settle_into_away", lambda w: (w.start(), w.go(minutes=26)), lambda w: w.run(services.sync), 1),
    ("settle_through_a_whole_break", lambda w: (w.start(), w.go(minutes=40)), lambda w: w.run(services.sync), 1),
    ("button_start_break", prepare_at_target, lambda w: tap(w, "start_break"), 1),
    ("button_pause", prepare_at_target, lambda w: tap(w, "pause"), 1),
    ("button_stale_version", prepare_at_target, lambda w: tap(w, "pause", version=w.timer.version + 1), 0),
    ("erase_with_timer", prepare_running, lambda w: w.run(services.delete_all_for_user), 1),
    ("erase_without_timer", prepare_nothing, lambda w: w.run(services.delete_all_for_user), 0),
]


@pytest.mark.parametrize("name, prepare, act, expected", CASES, ids=[c[0] for c in CASES])
def test_every_service_action_announces_exactly_once_when_it_moves_the_timer(w, name, prepare, act, expected):
    prepare(w)
    w.events.clear()
    act(w)
    assert len(w.events) == expected, w.events
    for payload in w.events:
        assert payload["user_id"] == str(USER) and payload["at"] == w.now


def test_a_refused_action_rolls_back_and_announces_nothing(w):
    w.start()
    w.events.clear()
    with pytest.raises(ConflictError):
        w.run(services.complete)  # the round has not finished
    with pytest.raises(ConflictError):
        w.run(services.extend, version=w.timer.version + 7)  # stale version
    assert w.events == []


def test_the_announcement_comes_after_the_commit_not_before(w, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        services.start(USER, client_id=uuid.uuid4())
    assert w.events == [] and len(callbacks) == 1  # held until the transaction commits
    callbacks[0]()
    assert len(w.events) == 1


def test_changing_settings_does_not_announce_because_a_running_phase_keeps_its_own_lengths(w):
    w.start()
    w.events.clear()
    before = ActiveTimer.objects.filter(pk=USER).values().get()
    services.update_settings(USER, {"preset": "deep", "overtime_enabled": True})
    assert w.events == [] and ActiveTimer.objects.filter(pk=USER).values().get() == before


def test_no_public_action_can_be_added_without_announcing_or_being_listed_here():
    """Guard for the next person who adds an action to `services`: announce it, or say why it cannot move the timer."""
    not_timer_actions = {"get_or_create_settings", "update_settings"}
    public = {
        name
        for name, fn in inspect.getmembers(services, inspect.isfunction)
        if not name.startswith("_") and fn.__module__ == services.__name__
    }
    announcing = {name for name in public if getattr(getattr(services, name), "announces_timer_changes", False)}
    assert public - announcing == not_timer_actions


# --- the payload ---------------------------------------------------------------------------------------------------


def last(w):
    return w.events[-1]


def test_a_running_focus_round_payload(w, scheme):
    from modules.syllabus.models import Subject

    subject = Subject.objects.get(key="taxation")
    t = w.start(subject_id=subject.id)
    p = last(w)
    assert p == {
        "user_id": str(USER),
        "active": True,
        "client_id": str(t.client_id),
        "version": 1,
        "phase": "focus",
        "ends_at": NOW + timedelta(minutes=25),
        "paused": False,
        "overtime": False,
        "round": 1,
        "minutes": 25,
        "subject_name": subject.name,
        "break_minutes": 5,
        "next_round": None,
        "away_pending": False,
        "at": NOW,
    }


def test_overtime_and_an_extension_show_in_the_payload(w):
    w.start(overtime=True)
    assert last(w)["overtime"] is True
    w.run(services.end, save=False)
    w.start()
    w.run(services.extend)
    p = last(w)
    assert (p["minutes"], p["version"], p["ends_at"], p["overtime"]) == (30, 2, NOW + timedelta(minutes=30), False)


def test_pause_removes_the_end_and_resume_restores_it_later(w):
    w.start()
    w.go(minutes=10)
    w.run(services.pause)
    assert (last(w)["paused"], last(w)["ends_at"]) == (True, None)
    w.go(minutes=3)
    w.run(services.resume)
    assert (last(w)["paused"], last(w)["ends_at"]) == (False, NOW + timedelta(minutes=28))


def test_the_break_payload_names_the_next_round(w):
    prepare_break(w)
    p = last(w)
    assert (p["phase"], p["minutes"], p["round"], p["next_round"], p["break_minutes"]) == ("short_break", 5, 1, 2, None)


def test_the_away_payload_says_so_and_has_no_end_to_wait_for(w):
    prepare_away(w)
    p = last(w)
    assert (p["away_pending"], p["ends_at"], p["overtime"]) == (True, None, False)


def test_when_the_timer_is_gone_the_payload_is_just_the_student_and_the_time(w):
    w.start()
    w.run(services.end, save=False)
    assert last(w) == {"user_id": str(USER), "active": False, "at": NOW}


def test_the_payload_is_small_and_carries_no_secrets(w):
    w.start()
    text = repr(last(w))
    assert len(text) < 700 and "token" not in text and "email" not in text
