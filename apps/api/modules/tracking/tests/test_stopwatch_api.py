import uuid
from datetime import timedelta

import pytest

from modules.tracking import services
from modules.tracking.models import ActiveStopwatch, DailyRollup, StudySession

from .conftest import NOW, USER, iso

pytestmark = pytest.mark.django_db


def start(api, **extra):
    body = {"client_id": str(uuid.uuid4()), **extra}
    return api.post("/tracking/stopwatch/start/", body), body["client_id"]


def test_nothing_is_running_at_first(api):
    res = api.get("/tracking/stopwatch/")
    assert res.status_code == 200
    assert res.json_body["stopwatch"] is None and res.json_body["live"] == "none"
    assert res.json_body["idle_minutes"] == 10 and res.json_body["server_time"]


def test_requires_a_signed_in_student(client):
    assert client.get("/api/v1/tracking/stopwatch/").status_code in (401, 403)


def test_start_stores_the_server_time_and_counts_up(api, clock, ids):
    res, cid = start(api, subject_id=ids["taxation"], chapter_id=ids["gst"], activity_type="reading")
    assert res.status_code == 201
    sw = res.json_body["stopwatch"]
    assert (sw["status"], sw["elapsed_seconds"], sw["version"], sw["client_id"]) == ("running", 0, 1, cid)
    assert (sw["subject_id"], sw["chapter_id"]) == (ids["taxation"], ids["gst"])
    assert res.json_body["live"] == "stopwatch"
    clock.advance(minutes=25)
    again = api.get("/tracking/stopwatch/").json_body["stopwatch"]
    assert again["elapsed_seconds"] == 1500


def test_default_activity_comes_from_settings(api):
    api.put("/tracking/settings/", {"default_activity_type": "practice"})
    assert start(api)[0].json_body["stopwatch"]["activity_type"] == "practice"


def test_only_one_stopwatch_and_a_retried_start_is_harmless(api):
    first, cid = start(api)
    retry = api.post("/tracking/stopwatch/start/", {"client_id": cid})
    assert (retry.status_code, retry.json_body["stopwatch"]["version"]) == (200, 1)
    second, _ = start(api)
    assert second.status_code == 409 and second.json_body["error"]["code"] == "timer_already_active"
    assert second.json_body["error"]["details"]["live"] == "stopwatch"
    assert ActiveStopwatch.objects.count() == 1


def test_start_validates_tags(api):
    assert start(api, subject_id=str(uuid.uuid4()))[0].status_code == 400
    assert start(api, activity_type="nap")[0].status_code == 400
    assert not ActiveStopwatch.objects.exists()


def test_pause_time_is_not_counted(api, clock):
    start(api)
    clock.advance(minutes=30)
    paused = api.post("/tracking/stopwatch/pause/", {"version": 1}).json_body["stopwatch"]
    assert (paused["status"], paused["elapsed_seconds"], paused["version"], paused["pause_count"]) == (
        "paused",
        1800,
        2,
        1,
    )
    clock.advance(minutes=10)
    assert api.get("/tracking/stopwatch/").json_body["stopwatch"]["elapsed_seconds"] == 1800  # frozen while paused
    resumed = api.post("/tracking/stopwatch/resume/", {"version": 2}).json_body["stopwatch"]
    assert (resumed["status"], resumed["paused_total_seconds"], resumed["version"]) == ("running", 600, 3)
    clock.advance(minutes=30)
    out = api.post("/tracking/stopwatch/stop/", {"version": 3}).json_body
    assert out["outcome"] == "saved"
    s = out["session"]
    assert (s["source"], s["focus_seconds"], s["paused_total_seconds"], s["pause_count"]) == ("stopwatch", 3600, 600, 1)
    assert not ActiveStopwatch.objects.exists()
    assert DailyRollup.objects.get(user_id=USER).seconds == 3600


def test_pause_after_an_hour_with_ten_minutes_paused_counts_fifty(api, clock):
    start(api)
    clock.advance(minutes=20)
    api.post("/tracking/stopwatch/pause/", {})
    clock.advance(minutes=10)
    api.post("/tracking/stopwatch/resume/", {})
    clock.advance(minutes=30)
    assert api.post("/tracking/stopwatch/stop/", {}).json_body["session"]["focus_seconds"] == 3000


def test_a_stale_version_answers_409_with_the_latest_state(api, clock):
    start(api)
    api.post("/tracking/stopwatch/pause/", {"version": 1})
    res = api.post("/tracking/stopwatch/resume/", {"version": 1})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "stale_version"
    assert res.json_body["error"]["details"]["stopwatch"]["version"] == 2
    assert api.patch("/tracking/stopwatch/context/", {"version": 1, "activity_type": "notes"}).status_code == 409


def test_replayed_pause_and_resume_without_a_version_are_idempotent(api, clock):
    start(api)
    clock.advance(minutes=5)
    api.post("/tracking/stopwatch/pause/", {})
    again = api.post("/tracking/stopwatch/pause/", {}).json_body["stopwatch"]
    assert again["pause_count"] == 1
    api.post("/tracking/stopwatch/resume/", {})
    assert api.post("/tracking/stopwatch/resume/", {}).json_body["stopwatch"]["status"] == "running"


def test_changing_the_context_while_running(api, ids):
    start(api)
    res = api.patch(
        "/tracking/stopwatch/context/", {"version": 1, "chapter_id": ids["gst"], "activity_type": "practice"}
    )
    sw = res.json_body["stopwatch"]
    assert (sw["subject_id"], sw["chapter_id"], sw["activity_type"], sw["version"]) == (
        ids["taxation"],
        ids["gst"],
        "practice",
        2,
    )
    bad = api.patch("/tracking/stopwatch/context/", {"version": 2, "subject_id": ids["laws"], "chapter_id": ids["gst"]})
    assert bad.status_code == 400


def test_under_a_minute_is_discarded_without_saving(api, clock):
    start(api)
    clock.advance(seconds=40)
    out = api.post("/tracking/stopwatch/stop/", {}).json_body
    assert (out["session"], out["outcome"]) == (None, "too_short")
    assert not StudySession.objects.exists() and not ActiveStopwatch.objects.exists()


def test_stop_without_saving_discards(api, clock):
    start(api)
    clock.advance(minutes=30)
    out = api.post("/tracking/stopwatch/stop/", {"save": False}).json_body
    assert out["outcome"] == "discarded" and not StudySession.objects.exists()


def test_a_replayed_stop_returns_the_saved_session_once(api, clock):
    _, cid = start(api)
    clock.advance(minutes=30)
    first = api.post("/tracking/stopwatch/stop/", {"client_id": cid}).json_body["session"]
    replay = api.post("/tracking/stopwatch/stop/", {"client_id": cid})
    assert replay.status_code == 200 and replay.json_body["session"]["id"] == first["id"]
    assert StudySession.objects.count() == 1
    assert api.post("/tracking/stopwatch/stop/", {}).status_code == 404
    assert api.post("/tracking/stopwatch/stop/", {"client_id": str(uuid.uuid4())}).status_code == 404
    assert api.post("/tracking/stopwatch/start/", {"client_id": cid}).json_body["error"]["code"] == "client_id_used"


def test_the_trim_on_stop_is_honoured_and_never_goes_past_now(api, clock):
    start(api)
    clock.advance(minutes=60)
    out = api.post("/tracking/stopwatch/stop/", {"end_at": iso(NOW + timedelta(minutes=45))}).json_body
    assert out["session"]["focus_seconds"] == 2700


def test_a_forgotten_stopwatch_is_trimmed_to_the_last_active_moment(api, clock):
    start(api)
    clock.advance(hours=2)
    api.get("/tracking/stopwatch/?alive=1&active=1")  # the student was last active two hours in
    clock.advance(hours=20)
    api.get("/tracking/stopwatch/?alive=1")  # the page was open but nobody touched it
    s = api.post("/tracking/stopwatch/stop/", {}).json_body["session"]
    assert (s["focus_seconds"], s["idle_trimmed"]) == (7200, True)


def test_the_idle_prompt_then_silence_pauses_at_the_last_active_time(api, clock):
    start(api)
    clock.advance(minutes=12)
    sw = api.get("/tracking/stopwatch/?alive=1").json_body["stopwatch"]
    assert sw["idle_due"] is True and sw["status"] == "running"
    prompted = api.post("/tracking/stopwatch/idle/", {"answer": "prompted"}).json_body["stopwatch"]
    assert prompted["idle_pending"] is True and prompted["version"] == 1  # the prompt is not a versioned change
    clock.advance(seconds=100)
    assert api.get("/tracking/stopwatch/").json_body["stopwatch"]["status"] == "running"
    clock.advance(seconds=30)
    paused = api.get("/tracking/stopwatch/").json_body["stopwatch"]
    assert (paused["status"], paused["elapsed_seconds"], paused["idle_pending"], paused["version"]) == (
        "paused",
        0,
        False,
        2,
    )
    # last active was the start, so nothing was earned; resuming starts counting again from now
    api.post("/tracking/stopwatch/resume/", {})
    clock.advance(minutes=30)
    assert api.post("/tracking/stopwatch/stop/", {}).json_body["session"]["focus_seconds"] == 1800


def test_answering_still_studying_clears_the_prompt(api, clock):
    start(api)
    clock.advance(minutes=12)
    api.post("/tracking/stopwatch/idle/", {"answer": "prompted"})
    clock.advance(seconds=60)
    ok = api.post("/tracking/stopwatch/idle/", {"answer": "still_studying"}).json_body["stopwatch"]
    assert ok["idle_pending"] is False and ok["idle_due"] is False
    clock.advance(seconds=300)
    assert api.get("/tracking/stopwatch/").json_body["stopwatch"]["status"] == "running"


def test_idle_prompt_can_be_switched_off(api, clock):
    api.put("/tracking/settings/", {"idle_minutes": 0})
    start(api)
    clock.advance(hours=3)
    assert api.get("/tracking/stopwatch/").json_body["stopwatch"]["idle_due"] is False


def test_an_offline_start_is_counted_from_the_moment_of_the_tap(api, clock):
    clock.advance(minutes=30)
    res, _ = start(api, at=iso(NOW + timedelta(minutes=5)))
    assert res.json_body["stopwatch"]["elapsed_seconds"] == 25 * 60
    api.post("/tracking/stopwatch/stop/", {"save": False})
    far, _ = start(api, at=iso(NOW - timedelta(days=3)))  # too old: clamped to twelve hours ago
    assert far.json_body["stopwatch"]["elapsed_seconds"] == 12 * 3600
    api.post("/tracking/stopwatch/stop/", {"save": False})
    future, _ = start(api, at=iso(NOW + timedelta(days=1)))
    assert future.json_body["stopwatch"]["elapsed_seconds"] == 0


def test_another_timer_blocks_the_stopwatch_through_the_registry(api):
    kind = {"value": None}
    provider = lambda user_id: kind["value"]  # noqa: E731
    services.register_live_timer_provider(provider)
    try:
        assert api.get("/tracking/stopwatch/").json_body["live"] == "none"
        kind["value"] = "pomodoro"
        assert api.get("/tracking/stopwatch/").json_body["live"] == "pomodoro"
        res, _ = start(api)
        assert res.status_code == 409
        assert (
            res.json_body["error"]["code"] == "timer_already_active"
            and res.json_body["error"]["details"]["live"] == "pomodoro"
        )
        assert not ActiveStopwatch.objects.exists()
        kind["value"] = None
        assert start(api)[0].status_code == 201
    finally:
        services._live_timer_providers.remove(provider)


def test_students_never_see_each_others_stopwatch(api, other_api):
    start(api)
    assert other_api.get("/tracking/stopwatch/").json_body["stopwatch"] is None
    assert other_api.post("/tracking/stopwatch/pause/", {}).status_code == 404
    assert start(other_api)[0].status_code == 201


def test_a_stopwatch_session_cannot_overlap_a_live_session_but_may_overlap_manual_time(api, clock):
    api.post(
        "/tracking/sessions/",
        {
            "client_id": str(uuid.uuid4()),
            "started_at": iso(NOW - timedelta(minutes=30)),
            "ended_at": iso(NOW + timedelta(minutes=3)),
        },
    )
    start(api)
    clock.advance(minutes=45)
    s = api.post("/tracking/stopwatch/stop/", {}).json_body["session"]
    assert s["overlaps_other"] is True  # kept, flagged: the student's tracked time is never thrown away
