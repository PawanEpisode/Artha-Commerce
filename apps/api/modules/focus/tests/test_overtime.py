"""Overtime: a focus round that reaches its planned length keeps counting until the student stops it."""

import uuid

import pytest

from modules.focus.models import ActiveTimer
from modules.tracking.models import StudySession

from .conftest import beat, start, timer

pytestmark = pytest.mark.django_db
P = "/focus/timer/"


@pytest.fixture
def round_(api):
    res, cid = start(api, overtime=True)
    assert res.status_code == 201 and res.json_body["timer"]["overtime_enabled"] is True
    return cid


def stay(api, clock, **delta):
    """Moves the clock in steps no longer than the heartbeat window, with the tab open the whole time."""
    seconds = int(clock_seconds(delta))
    while seconds > 0:
        step = min(seconds, 110)
        clock.advance(seconds=step)
        beat(api)
        seconds -= step


def clock_seconds(delta):
    return delta.get("minutes", 0) * 60 + delta.get("seconds", 0)


def test_the_round_keeps_running_past_zero_and_counts_the_extra_time(api, clock, round_):
    stay(api, clock, minutes=27)
    t = timer(api)["timer"]
    assert (t["phase"], t["status"]) == ("focus", "running")
    assert t["remaining_seconds"] == 0 and t["overtime_seconds"] == 120 and t["can_extend"] is False
    assert not StudySession.objects.exists()  # nothing is saved until the student stops


def test_complete_at_zero_does_not_close_or_start_a_break(api, clock, round_):
    stay(api, clock, minutes=25)
    res = api.post(P + "complete/")
    assert res.status_code == 200 and res.json_body["timer"]["phase"] == "focus"
    assert not StudySession.objects.exists()


def test_stop_and_save_counts_the_full_time_and_starts_the_break(api, clock, round_):
    stay(api, clock, minutes=31)
    res = api.post(P + "end/", {"client_id": round_})
    body = res.json_body
    assert body["outcome"] == "completed" and body["session"]["focus_seconds"] == 31 * 60
    assert body["timer"]["phase"] == "short_break" and body["timer"]["round_number"] == 1
    s = StudySession.objects.get()
    assert (s.status, s.focus_seconds, s.planned_seconds, s.auto_closed) == ("completed", 31 * 60, 1500, False)


def test_with_breaks_set_to_manual_the_break_waits_after_stop_and_save(api, clock):
    api.put("/focus/settings/", {"auto_start_breaks": False})
    start(api, overtime=True)
    stay(api, clock, minutes=26)
    body = api.post(P + "end/", {}).json_body
    assert body["outcome"] == "completed" and body["timer"] is None
    assert body["idle"]["next_phase"] == "short_break" and body["idle"]["next_round"] == 1


def test_stopping_before_the_planned_length_is_still_an_early_end(api, clock, round_):
    stay(api, clock, minutes=10)
    body = api.post(P + "end/", {"reason": "tired"}).json_body
    assert body["outcome"] == "saved" and body["timer"] is None
    assert StudySession.objects.get().status == "partial"


def test_discarding_in_overtime_saves_nothing_and_starts_no_break(api, clock, round_):
    stay(api, clock, minutes=30)
    body = api.post(P + "end/", {"save": False}).json_body
    assert body["outcome"] == "discarded" and body["timer"] is None
    assert not StudySession.objects.exists()


def test_a_pause_in_overtime_stops_the_extra_time(api, clock, round_):
    stay(api, clock, minutes=28)
    api.post(P + "pause/")
    clock.advance(hours=1)
    t = timer(api)["timer"]
    assert t["status"] == "paused" and t["overtime_seconds"] == 180
    api.post(P + "resume/")
    stay(api, clock, minutes=2)
    assert timer(api)["timer"]["overtime_seconds"] == 300


def test_a_student_who_leaves_in_overtime_is_closed_at_the_last_sighting(api, clock, round_):
    stay(api, clock, minutes=30)  # five minutes over, then the tab closes
    clock.advance(hours=1)
    body = timer(api)
    assert body["timer"] is None
    s = StudySession.objects.get()
    assert s.auto_closed is True and s.status == "completed" and s.focus_seconds == 30 * 60


def test_overtime_is_capped(api, clock, round_):
    stay(api, clock, minutes=25 + 120 + 5)
    assert timer(api)["timer"] is None
    assert (25 + 118) * 60 <= StudySession.objects.get().focus_seconds <= (25 + 120) * 60


def test_a_round_nobody_watched_at_the_end_still_asks_whether_it_counted(api, clock, round_):
    clock.advance(minutes=40)
    t = timer(api)["timer"]
    assert t["status"] == "away" and t["overtime_seconds"] == 0


def test_extending_is_refused_once_the_round_is_in_overtime(api, clock, round_):
    stay(api, clock, minutes=26)
    res = api.post(P + "extend/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "not_extendable"


def test_turning_the_setting_off_keeps_the_classic_behaviour(api, clock):
    start(api, overtime=False)
    stay(api, clock, minutes=25)
    assert timer(api)["timer"]["phase"] == "short_break"
    assert StudySession.objects.get().focus_seconds == 1500


def test_a_timer_started_before_the_setting_existed_keeps_the_classic_behaviour(api, clock):
    start(api, overtime=False)
    ActiveTimer.objects.update(overtime_enabled=False)
    stay(api, clock, minutes=26)
    assert timer(api)["timer"]["phase"] == "short_break"


def test_a_second_stop_is_idempotent(api, clock, round_):
    stay(api, clock, minutes=26)
    api.post(P + "end/", {"client_id": round_})
    again = api.post(P + "end/", {"client_id": round_})
    assert again.status_code == 200 and again.json_body["outcome"] == "saved"
    assert StudySession.objects.count() == 1
    assert uuid.UUID(round_)
