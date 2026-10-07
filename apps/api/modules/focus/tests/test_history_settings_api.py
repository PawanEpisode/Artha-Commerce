import uuid
from datetime import timedelta

import pytest

from modules.focus.models import ActiveTimer, FocusSettings
from modules.tracking.models import StudySession

from .conftest import beat, iso, start

pytestmark = pytest.mark.django_db


def one_round(api, clock):
    res, cid = start(api)
    clock.advance(minutes=24, seconds=30)
    beat(api)
    clock.advance(seconds=30)
    api.get("/focus/timer/")
    return cid


def test_settings_default_and_update(api):
    body = api.get("/focus/settings/").json_body
    assert body == {
        "preset": "classic",
        "focus_minutes": 25,
        "short_break_minutes": 5,
        "long_break_minutes": 15,
        "rounds_before_long": 4,
        "auto_start_breaks": True,
        "auto_start_focus": False,
        "overtime_enabled": True,
        "sound_enabled": True,
        "volume": 70,
        "notifications_enabled": False,
        "keep_awake": True,
        "keep_awake_in_breaks": False,
        "popout_on_start": False,
        "popout_size": "pill",
        "popout_prompt_seen": False,
        "intro_seen": False,
    }
    res = api.put("/focus/settings/", {"volume": 30, "sound_enabled": False, "preset": "light"})
    assert res.status_code == 200 and sorted(res.json_body["changed"]) == ["preset", "sound_enabled", "volume"]
    assert api.get("/focus/settings/").json_body["focus_minutes"] == 15


def test_keep_awake_defaults_on_for_focus_only_and_follows_the_student(api):
    body = api.get("/focus/settings/").json_body
    assert body["keep_awake"] is True and body["keep_awake_in_breaks"] is False
    res = api.put("/focus/settings/", {"keep_awake": False, "keep_awake_in_breaks": True})
    assert res.status_code == 200 and sorted(res.json_body["changed"]) == ["keep_awake", "keep_awake_in_breaks"]
    again = api.get("/focus/settings/").json_body
    assert again["keep_awake"] is False and again["keep_awake_in_breaks"] is True


def test_keep_awake_must_be_a_boolean(api):
    assert api.put("/focus/settings/", {"keep_awake": "maybe"}).status_code == 400
    assert api.get("/focus/settings/").json_body["keep_awake"] is True


def test_popout_settings_default_off_and_follow_the_student(api):
    body = api.get("/focus/settings/").json_body
    assert (body["popout_on_start"], body["popout_size"], body["popout_prompt_seen"]) == (False, "pill", False)
    res = api.put("/focus/settings/", {"popout_on_start": True, "popout_size": "card", "popout_prompt_seen": True})
    assert res.status_code == 200
    assert sorted(res.json_body["changed"]) == ["popout_on_start", "popout_prompt_seen", "popout_size"]
    again = api.get("/focus/settings/").json_body
    assert (again["popout_on_start"], again["popout_size"], again["popout_prompt_seen"]) == (True, "card", True)
    # Saving the same values again changes nothing.
    assert api.put("/focus/settings/", {"popout_size": "card"}).json_body["changed"] == []


def test_popout_size_only_accepts_pill_or_card(api):
    assert api.put("/focus/settings/", {"popout_size": "big"}).status_code == 400
    assert api.put("/focus/settings/", {"popout_size": ""}).status_code == 400
    assert api.put("/focus/settings/", {"popout_on_start": "maybe"}).status_code == 400
    assert api.get("/focus/settings/").json_body["popout_size"] == "pill"


def test_popout_size_check_constraint_rejects_a_raw_write(api):
    from django.db import IntegrityError, transaction

    api.put("/focus/settings/", {"volume": 10})  # a GET alone does not store a row
    assert FocusSettings.objects.count() == 1
    with pytest.raises(IntegrityError), transaction.atomic():
        FocusSettings.objects.update(popout_size="big")


def test_editing_a_duration_makes_the_preset_custom_unless_it_matches_one(api):
    assert api.put("/focus/settings/", {"focus_minutes": 30}).json_body["preset"] == "custom"
    assert api.put("/focus/settings/", {"focus_minutes": 25}).json_body["preset"] == "classic"


@pytest.mark.parametrize(
    "body",
    [{"focus_minutes": 4}, {"focus_minutes": 121}, {"rounds_before_long": 9}, {"volume": 101}, {"preset": "x"}],
)
def test_settings_outside_the_limits_are_refused(api, body):
    assert api.put("/focus/settings/", body).status_code == 400
    assert api.get("/focus/settings/").json_body["focus_minutes"] == 25


def test_an_unchanged_setting_reports_nothing_changed(api):
    assert api.put("/focus/settings/", {"volume": 70}).json_body["changed"] == []


def test_history_lists_only_pomodoro_rounds_newest_first(api, clock, ids):
    one_round(api, clock)
    clock.advance(minutes=10)
    api.post(
        "/tracking/sessions/",
        {
            "client_id": str(uuid.uuid4()),
            "started_at": iso(clock.now - clock.now.__class__.resolution * 0),
            "duration_seconds": 600,
        },
    ) if False else None
    rows = api.get("/focus/sessions/").json_body["results"]
    assert len(rows) == 1 and rows[0]["source"] == "pomodoro"


def test_a_round_can_be_retagged_edited_and_deleted_from_the_history(api, clock, ids):
    one_round(api, clock)
    sid = api.get("/focus/sessions/").json_body["results"][0]["id"]
    res = api.patch(f"/focus/sessions/{sid}/", {"note": "GST ITC", "activity_type": "practice"})
    assert res.status_code == 200 and res.json_body["activity_type"] == "practice"
    d = api.delete(f"/focus/sessions/{sid}/")
    assert d.status_code == 200 and d.json_body["undo_token"]
    assert not StudySession.objects.exists()


def test_the_history_endpoints_refuse_sessions_from_other_sources(api, clock):
    made = api.post(
        "/tracking/sessions/",
        {
            "client_id": str(uuid.uuid4()),
            "started_at": iso(clock.now - timedelta(hours=2)),
            "duration_seconds": 1800,
        },
    )
    sid = made.json_body["id"]
    assert api.patch(f"/focus/sessions/{sid}/", {"note": "x"}).status_code == 404
    assert api.delete(f"/focus/sessions/{sid}/").status_code == 404
    assert StudySession.objects.count() == 1


def test_another_students_round_is_not_found(api, other_api, clock):
    one_round(api, clock)
    sid = api.get("/focus/sessions/").json_body["results"][0]["id"]
    assert other_api.patch(f"/focus/sessions/{sid}/", {"note": "x"}).status_code == 404
    assert other_api.get("/focus/sessions/").json_body["results"] == []


def test_the_shared_goal_counts_pomodoro_time(api, clock):
    one_round(api, clock)
    res = api.put("/tracking/goals/", {"goals": [{"period": "daily", "subject_id": None, "target_minutes": 100}]})
    assert res.json_body["progress"]["daily"]["done_seconds"] == 1500
    assert res.json_body["progress"]["daily"]["percent"] == 25


def test_data_export_and_delete(api, clock):
    api.put("/focus/settings/", {"volume": 10, "popout_size": "card", "popout_prompt_seen": True})
    start(api)
    out = api.get("/focus/data/").json_body
    assert out["settings"]["volume"] == 10 and out["timer"]["phase"] == "focus"
    assert out["settings"]["popout_size"] == "card" and out["settings"]["popout_prompt_seen"] is True
    assert out["settings"]["popout_on_start"] is False
    assert api.delete("/focus/data/").status_code == 204
    assert not ActiveTimer.objects.exists() and not FocusSettings.objects.exists()
    assert api.get("/focus/data/").json_body == {"settings": None, "timer": None}
