"""Opt-in auto capture (F-01.2 Q1): off by default, never fights a live timer, capped, not forwarded to coverage."""

import uuid
from datetime import timedelta

import pytest

from modules.coverage.models import CoverageEvent
from modules.tracking.models import StudySession

from .conftest import NOW, iso, manual

pytestmark = pytest.mark.django_db


def auto(api, ids, minutes=10, ago=15, **extra):
    body = {
        "client_id": str(uuid.uuid4()),
        "chapter_id": ids["gst"],
        "started_at": iso(NOW - timedelta(minutes=ago)),
        "seconds": minutes * 60,
        **extra,
    }
    return api.post("/tracking/auto/", body)


@pytest.fixture
def on(api):
    api.put("/tracking/settings/", {"auto_capture_enabled": True})


def test_it_is_off_until_the_student_turns_it_on(api, ids):
    assert api.get("/tracking/settings/").json_body["auto_capture_enabled"] is False
    res = auto(api, ids)
    assert res.status_code == 409 and res.json_body["error"]["code"] == "auto_capture_off"
    assert not StudySession.objects.exists()


def test_it_logs_chapter_time_as_an_auto_session(api, ids, on):
    res = auto(api, ids, minutes=10)
    assert res.status_code == 201 and res.json_body["outcome"] == "saved"
    s = StudySession.objects.get()
    assert (s.source, s.focus_seconds, s.status, s.activity_type) == ("auto", 600, "completed", "reading")
    assert str(s.chapter_id) == ids["gst"] and str(s.subject_id) == ids["taxation"]
    assert s.round_number is None and s.cycle_id is None


def test_a_retried_post_is_harmless(api, ids, on):
    body = {
        "client_id": str(uuid.uuid4()),
        "chapter_id": ids["gst"],
        "started_at": iso(NOW - timedelta(minutes=20)),
        "seconds": 600,
    }
    first = api.post("/tracking/auto/", body)
    again = api.post("/tracking/auto/", body)
    assert first.status_code == 201 and again.json_body["session"]["id"] == first.json_body["session"]["id"]
    assert StudySession.objects.count() == 1


def test_auto_time_is_not_forwarded_to_coverage(api, ids, on):
    auto(api, ids)
    assert not CoverageEvent.objects.filter(type="study_time").exists()


def test_auto_time_counts_toward_the_daily_totals(api, ids, on):
    auto(api, ids, minutes=10)
    assert api.get("/tracking/reports/summary/").json_body["total_seconds"] == 600
    assert api.get("/tracking/sessions/?source=auto").json_body["results"][0]["source"] == "auto"


def test_less_than_a_minute_is_not_saved(api, ids, on):
    res = api.post(
        "/tracking/auto/",
        {
            "client_id": str(uuid.uuid4()),
            "chapter_id": ids["gst"],
            "started_at": iso(NOW - timedelta(seconds=30)),
            "seconds": 30,
        },
    )
    assert res.status_code == 200 and res.json_body["outcome"] == "too_short"


def test_a_post_cannot_run_into_the_future(api, ids, on):
    res = auto(api, ids, minutes=10, ago=3)
    assert res.json_body["session"]["focus_seconds"] == 180


def test_one_post_covers_at_most_thirty_minutes(api, ids, on):
    assert auto(api, ids, minutes=31).status_code == 400


def test_a_running_timer_wins(api, ids, on):
    api.post("/tracking/stopwatch/start/", {"client_id": str(uuid.uuid4())})
    res = auto(api, ids)
    assert res.json_body["outcome"] == "timer_running" and not StudySession.objects.exists()


def test_a_running_pomodoro_wins_too(api, ids, on):
    api.post("/focus/timer/start/", {"client_id": str(uuid.uuid4())})
    assert auto(api, ids).json_body["outcome"] == "timer_running"


def test_time_that_overlaps_recorded_time_is_skipped(api, ids, on):
    manual(api, NOW - timedelta(minutes=30), NOW - timedelta(minutes=10))
    res = auto(api, ids, minutes=10, ago=15)
    assert res.json_body["outcome"] == "overlap" and StudySession.objects.count() == 1


def test_auto_time_stops_at_four_hours_a_day(api, ids, on):
    for n in range(8):
        res = api.post(
            "/tracking/auto/",
            {
                "client_id": str(uuid.uuid4()),
                "chapter_id": ids["gst"],
                "started_at": iso(NOW - timedelta(minutes=35 + 30 * (8 - n))),
                "seconds": 1800,
            },
        )
        assert res.json_body["outcome"] == "saved", n
    last = auto(api, ids, minutes=10, ago=15)
    assert last.json_body["outcome"] == "daily_cap"


def test_unknown_chapters_and_other_students(api, other_api, ids, on):
    assert auto(api, ids, chapter_id=str(uuid.uuid4())).status_code == 400
    assert other_api.get("/tracking/sessions/?source=auto").json_body["results"] == []


def test_turning_it_off_keeps_what_was_logged_and_stops_new_logging(api, ids, on):
    auto(api, ids)
    api.put("/tracking/settings/", {"auto_capture_enabled": False})
    assert auto(api, ids, ago=40).status_code == 409
    assert StudySession.objects.count() == 1
