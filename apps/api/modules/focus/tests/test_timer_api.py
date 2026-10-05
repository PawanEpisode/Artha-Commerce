import uuid
from datetime import timedelta

import pytest

from modules.focus.models import ActiveTimer, FocusSettings
from modules.tracking.models import StudySession

from .conftest import NOW, beat, start, timer

pytestmark = pytest.mark.django_db
P = "/focus/timer/"


def finish_present(api, clock, minutes=25):
    """Runs a round to its end with the student watching (heartbeat 30 s before the end)."""
    clock.advance(minutes=minutes, seconds=-30)
    beat(api)
    clock.advance(seconds=30)


def test_requires_a_signed_in_student(client):
    assert client.get("/api/v1/focus/timer/").status_code in (401, 403)


def test_nothing_is_running_at_first(api):
    body = timer(api)
    assert body["timer"] is None and body["live"] == "none" and body["server_time"]
    assert body["idle"] == {"next_phase": "focus", "next_round": 1, "rounds_before_long": 4, "cycle_id": None}
    assert body["settings"]["preset"] == "classic" and body["settings"]["auto_start_breaks"] is True


def test_start_runs_a_classic_round_on_the_server_clock(api, clock, ids):
    res, cid = start(api, subject_id=ids["taxation"], chapter_id=ids["gst"], activity_type="practice")
    assert res.status_code == 201
    t = res.json_body["timer"]
    assert (t["phase"], t["status"], t["round_number"], t["planned_seconds"], t["remaining_seconds"]) == (
        "focus",
        "running",
        1,
        1500,
        1500,
    )
    assert (t["subject_id"], t["chapter_id"], t["activity_type"], t["client_id"]) == (
        ids["taxation"],
        ids["gst"],
        "practice",
        cid,
    )
    assert res.json_body["live"] == "pomodoro"
    clock.advance(minutes=10, seconds=3)
    assert timer(api)["timer"]["remaining_seconds"] == 897  # a refresh at 10:03 shows 14:57


def test_a_retried_start_changes_nothing(api, running):
    t, cid = running
    again = api.post(P + "start/", {"client_id": cid})
    assert (again.status_code, again.json_body["timer"]["version"]) == (200, t["version"])
    assert ActiveTimer.objects.count() == 1


def test_only_one_timer_at_a_time(api, running):
    res, _ = start(api)
    assert res.status_code == 409 and res.json_body["error"]["code"] == "timer_already_active"
    assert res.json_body["error"]["details"]["live"] == "pomodoro"


def test_a_running_stopwatch_blocks_a_round_and_a_round_blocks_the_stopwatch(api):
    api.post("/tracking/stopwatch/start/", {"client_id": str(uuid.uuid4())})
    res, _ = start(api)
    assert res.status_code == 409 and res.json_body["error"]["details"]["live"] == "stopwatch"
    api.post("/tracking/stopwatch/stop/", {"save": False})
    assert start(api)[0].status_code == 201
    other = api.post("/tracking/stopwatch/start/", {"client_id": str(uuid.uuid4())})
    assert other.status_code == 409 and other.json_body["error"]["details"]["live"] == "pomodoro"


def test_start_validates_tags_activity_and_presets(api):
    assert start(api, subject_id=str(uuid.uuid4()))[0].status_code == 400
    assert start(api, activity_type="nap")[0].status_code == 400
    assert start(api, preset="marathon")[0].status_code == 400
    assert (
        start(
            api, preset="custom", focus_minutes=4, short_break_minutes=5, long_break_minutes=15, rounds_before_long=4
        )[0].status_code
        == 400
    )
    assert not ActiveTimer.objects.exists()


def test_presets_and_custom_timings_set_the_length_and_are_remembered(api, clock):
    res, _ = start(api, preset="deep")
    assert res.json_body["timer"]["planned_seconds"] == 3000 and res.json_body["settings"]["preset"] == "deep"
    api.post(P + "end/", {"save": False})
    res, _ = start(
        api, preset="custom", focus_minutes=40, short_break_minutes=7, long_break_minutes=25, rounds_before_long=2
    )
    assert res.json_body["timer"]["planned_seconds"] == 2400
    assert FocusSettings.objects.get().last_preset == "custom"


def test_pause_freezes_the_countdown_and_resume_keeps_the_pause_out_of_the_round(api, clock, running):
    clock.advance(minutes=10)
    p = api.post(P + "pause/", {"version": running[0]["version"]})
    assert p.json_body["timer"]["status"] == "paused" and p.json_body["timer"]["remaining_seconds"] == 900
    clock.advance(minutes=5)
    assert timer(api)["timer"]["remaining_seconds"] == 900
    r = api.post(P + "resume/", {"version": p.json_body["timer"]["version"]})
    t = r.json_body["timer"]
    assert (t["status"], t["paused_total_seconds"], t["pause_count"], t["remaining_seconds"]) == (
        "running",
        300,
        1,
        900,
    )


def test_pause_and_resume_are_idempotent_without_a_version(api, clock, running):
    clock.advance(minutes=1)
    api.post(P + "pause/")
    again = api.post(P + "pause/")
    assert again.status_code == 200 and again.json_body["timer"]["pause_count"] == 1
    api.post(P + "resume/")
    assert api.post(P + "resume/").json_body["timer"]["status"] == "running"


def test_a_stale_version_returns_the_latest_timer(api, running):
    t, _ = running
    api.post(P + "pause/", {"version": t["version"]})
    res = api.post(P + "extend/", {"version": t["version"]})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "stale_version"
    assert res.json_body["error"]["details"]["timer"]["status"] == "paused"


def test_extend_adds_five_minutes_up_to_three_times(api, running):
    for n in (1, 2, 3):
        res = api.post(P + "extend/")
        assert res.json_body["timer"]["planned_seconds"] == 1500 + 300 * n
    assert res.json_body["timer"]["can_extend"] is False
    again = api.post(P + "extend/")
    assert again.status_code == 409 and again.json_body["error"]["code"] == "extension_limit"


def test_a_present_student_finishes_the_round_and_the_break_starts(api, clock, running):
    finish_present(api, clock)
    t = timer(api)["timer"]
    assert (t["phase"], t["round_number"], t["planned_seconds"], t["remaining_seconds"]) == ("short_break", 1, 300, 300)
    s = StudySession.objects.get()
    assert (s.source, s.status, s.focus_seconds, s.round_number, s.planned_seconds) == (
        "pomodoro",
        "completed",
        1500,
        1,
        1500,
    )
    assert s.auto_closed and s.presence_verified and s.cycle_id == uuid.UUID(t["cycle_id"])
    assert s.client_id == uuid.UUID(running[1])


def test_the_break_is_back_dated_to_the_end_of_the_round(api, clock, running):
    finish_present(api, clock)
    clock.advance(minutes=1, seconds=40)  # still inside the 5 minute break, seen late
    t = timer(api)["timer"]
    assert t["phase"] == "short_break" and t["remaining_seconds"] == 200


def test_a_paused_round_does_not_end_on_its_own(api, clock, running):
    clock.advance(minutes=5)
    api.post(P + "pause/")
    clock.advance(hours=3)
    t = timer(api)["timer"]
    assert t["status"] == "paused" and t["remaining_seconds"] == 1200
    assert not StudySession.objects.exists()


def test_the_client_can_complete_at_zero_and_the_round_counts_as_attended(api, clock, running):
    clock.advance(minutes=25, seconds=-1)  # one second of clock disagreement is tolerated
    res = api.post(P + "complete/")
    assert res.json_body["timer"]["phase"] == "short_break"
    s = StudySession.objects.get()
    assert s.auto_closed is False and s.presence_verified is True and s.focus_seconds == 1500


def test_completing_too_early_is_refused(api, clock, running):
    clock.advance(minutes=20)
    res = api.post(P + "complete/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "not_finished"
    assert not StudySession.objects.exists()


def test_completing_twice_does_not_save_twice(api, clock, running):
    clock.advance(minutes=25)
    api.post(P + "complete/")
    api.post(P + "complete/")  # the break is still running: refused, nothing written
    assert StudySession.objects.count() == 1


def test_a_student_who_was_away_decides_whether_the_round_counts(api, clock, running):
    clock.advance(minutes=27)
    t = timer(api)["timer"]
    assert t["status"] == "away" and t["away_pending"] and t["phase"] == "focus"
    assert not StudySession.objects.exists()
    res = api.post(P + "claim/", {"count": True})
    assert res.json_body["outcome"] == "counted"
    s = StudySession.objects.get()
    assert (s.focus_seconds, s.presence_verified, s.auto_closed) == (1500, False, False)
    assert res.json_body["timer"]["phase"] == "short_break" and res.json_body["timer"]["remaining_seconds"] == 180


def test_claiming_after_the_break_also_ran_out_leaves_the_timer_idle_with_the_cycle_kept(api, clock, running):
    clock.advance(minutes=60)
    res = api.post(P + "claim/", {"count": True})
    assert res.json_body["timer"] is None
    assert res.json_body["idle"]["next_round"] == 2 and res.json_body["idle"]["next_phase"] == "focus"


def test_discarding_an_away_round_saves_nothing_and_repeats_the_round(api, clock, running):
    clock.advance(minutes=40)
    res = api.post(P + "claim/", {"count": False})
    assert res.json_body["outcome"] == "discarded" and res.json_body["timer"] is None
    assert res.json_body["idle"]["next_round"] == 1
    assert not StudySession.objects.exists() and not ActiveTimer.objects.exists()


def test_away_blocks_other_actions_until_answered(api, clock, running):
    clock.advance(minutes=40)
    assert api.post(P + "extend/").json_body["error"]["code"] == "not_extendable"
    assert api.post(P + "pause/").json_body["error"]["code"] == "not_pausable"
    assert api.post(P + "end/", {}).status_code == 409


def test_claim_with_nothing_to_claim_is_harmless(api):
    res = api.post(P + "claim/", {"count": True})
    assert res.status_code == 200 and res.json_body["outcome"] == "none"


def test_a_heartbeat_keeps_the_student_present_but_never_changes_the_version(api, clock, running):
    clock.advance(minutes=1)
    v = beat(api).json_body["timer"]["version"]
    assert v == running[0]["version"]
    assert ActiveTimer.objects.get().last_seen_at == clock.now


def test_break_ending_with_auto_start_focus_off_goes_idle_and_remembers_the_round(api, clock, running):
    finish_present(api, clock)
    clock.advance(minutes=5)
    body = timer(api)
    assert body["timer"] is None and body["live"] == "none"
    assert body["idle"]["next_round"] == 2 and body["idle"]["cycle_id"]
    res, _ = start(api)
    assert res.json_body["timer"]["round_number"] == 2
    assert res.json_body["timer"]["cycle_id"] == body["idle"]["cycle_id"]


def test_auto_start_focus_begins_the_next_round_when_the_student_is_there(api, clock):
    api.put("/focus/settings/", {"auto_start_focus": True})
    start(api)
    finish_present(api, clock)
    clock.advance(minutes=5, seconds=-30)
    beat(api)
    clock.advance(seconds=30)
    t = timer(api)["timer"]
    assert (t["phase"], t["round_number"]) == ("focus", 2)


def test_auto_start_focus_waits_when_the_student_has_left(api, clock):
    api.put("/focus/settings/", {"auto_start_focus": True})
    start(api)
    finish_present(api, clock)
    clock.advance(minutes=30)
    assert timer(api)["timer"] is None


def test_auto_start_breaks_off_waits_for_the_student_to_start_the_break(api, clock):
    api.put("/focus/settings/", {"auto_start_breaks": False})
    start(api)
    finish_present(api, clock)
    body = timer(api)
    assert body["timer"] is None and body["idle"]["next_phase"] == "short_break" and body["idle"]["next_round"] == 1
    res, _ = start(api, phase="short_break")
    assert res.status_code == 201 and res.json_body["timer"]["phase"] == "short_break"
    assert res.json_body["timer"]["planned_seconds"] == 300


def test_starting_a_round_instead_of_the_due_break_skips_the_break(api, clock):
    api.put("/focus/settings/", {"auto_start_breaks": False})
    start(api)
    finish_present(api, clock)
    res, _ = start(api)
    assert res.json_body["timer"]["phase"] == "focus" and res.json_body["timer"]["round_number"] == 2


def test_asking_for_a_break_that_is_not_due_is_refused(api):
    res, _ = start(api, phase="long_break")
    assert res.status_code == 400 and res.json_body["error"]["code"] == "no_break_due"


def test_the_long_break_follows_the_last_round_and_a_new_cycle_follows_it(api, clock):
    api.put(
        "/focus/settings/",
        {
            "preset": "custom",
            "focus_minutes": 5,
            "short_break_minutes": 1,
            "long_break_minutes": 5,
            "rounds_before_long": 2,
        },
    )
    first_cycle = None
    for expected in ("short_break", "long_break"):
        start(api)
        finish_present(api, clock, minutes=5)
        t = timer(api)["timer"]
        assert t["phase"] == expected
        first_cycle = first_cycle or t["cycle_id"]
        assert t["cycle_id"] == first_cycle
        clock.advance(minutes=t["planned_seconds"] // 60)
    body = timer(api)
    assert body["timer"] is None and body["idle"]["next_round"] == 1 and body["idle"]["cycle_id"] is None
    assert StudySession.objects.count() == 2


def test_the_cycle_is_forgotten_after_four_idle_hours(api, clock, running):
    finish_present(api, clock)
    clock.advance(minutes=5)
    assert timer(api)["idle"]["next_round"] == 2
    clock.advance(hours=4, seconds=1)
    assert timer(api)["idle"]["next_round"] == 1


def test_skipping_a_break_ends_it(api, clock, running):
    finish_present(api, clock)
    res = api.post(P + "skip-break/")
    assert res.json_body["timer"] is None and res.json_body["idle"]["next_round"] == 2


def test_skipping_when_no_break_is_running_is_refused(api, running):
    res = api.post(P + "skip-break/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "not_a_break"


def test_ending_early_can_save_a_partial_round_with_a_reason(api, clock, running):
    clock.advance(minutes=12)
    res = api.post(P + "end/", {"save": True, "reason": "tired", "client_id": running[1]})
    assert res.json_body["outcome"] == "saved" and res.json_body["timer"] is None
    s = StudySession.objects.get()
    assert (s.status, s.focus_seconds, s.interruption_reason, s.round_number) == ("partial", 720, "tired", 1)
    assert res.json_body["session"]["id"] == str(s.id)
    assert res.json_body["idle"]["next_round"] == 1  # the round was not finished, so it repeats


def test_ending_early_counts_only_the_time_before_a_pause(api, clock, running):
    clock.advance(minutes=10)
    api.post(P + "pause/")
    clock.advance(minutes=30)
    api.post(P + "end/", {"save": True})
    assert StudySession.objects.get().focus_seconds == 600


def test_ending_early_can_discard(api, clock, running):
    clock.advance(minutes=12)
    res = api.post(P + "end/", {"save": False})
    assert res.json_body["outcome"] == "discarded" and not StudySession.objects.exists()


def test_a_round_under_a_minute_is_never_saved(api, clock, running):
    clock.advance(seconds=59)
    res = api.post(P + "end/", {"save": True})
    assert res.json_body["outcome"] == "too_short" and not StudySession.objects.exists()


def test_an_unknown_reason_is_refused(api, running):
    assert api.post(P + "end/", {"reason": "bored"}).status_code == 400


def test_a_repeated_end_returns_the_saved_session(api, clock, running):
    clock.advance(minutes=12)
    api.post(P + "end/", {"save": True, "client_id": running[1]})
    again = api.post(P + "end/", {"save": True, "client_id": running[1]})
    assert again.status_code == 200 and again.json_body["outcome"] == "saved"
    assert StudySession.objects.count() == 1
    assert api.post(P + "end/", {"save": True}).status_code == 404


def test_the_context_can_change_while_running(api, running, ids):
    res = api.patch(
        P + "context/", {"version": running[0]["version"], "subject_id": ids["taxation"], "chapter_id": ids["gst"]}
    )
    assert (
        res.json_body["timer"]["chapter_id"] == ids["gst"]
        and res.json_body["timer"]["version"] == running[0]["version"] + 1
    )
    assert api.patch(P + "context/", {"version": 1, "activity_type": "revision"}).status_code == 409


def test_a_saved_round_reaches_the_tracker_and_coverage(api, clock, ids):
    start(api, subject_id=ids["taxation"], chapter_id=ids["gst"])
    finish_present(api, clock)
    timer(api)
    s = StudySession.objects.get()
    assert s.chapter_id and s.subject_id
    rows = api.get("/tracking/sessions/?source=pomodoro").json_body["results"]
    assert len(rows) == 1 and rows[0]["source"] == "pomodoro"


def test_an_offline_start_uses_the_time_of_the_tap(api, clock):
    at = NOW - timedelta(minutes=3)
    res, _ = start(api, at=at.isoformat().replace("+00:00", "Z"))
    assert res.json_body["timer"]["remaining_seconds"] == 1500 - 180


def test_another_student_never_sees_the_timer(api, other_api, running):
    assert timer(other_api)["timer"] is None
    assert other_api.post(P + "extend/").status_code == 404
    assert other_api.post(P + "end/", {}).status_code == 404
