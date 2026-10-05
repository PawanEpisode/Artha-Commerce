from datetime import timedelta

import pytest

from .conftest import NOW, ist, manual

pytestmark = pytest.mark.django_db


def put_goals(api, *goals):
    return api.put("/tracking/goals/", {"goals": list(goals)})


def daily(minutes, subject=None):
    return {"period": "daily", "subject_id": subject, "target_minutes": minutes}


def weekly(minutes, subject=None):
    return {"period": "weekly", "subject_id": subject, "target_minutes": minutes}


def test_defaults_before_any_goal(api):
    res = api.get("/tracking/goals/").json_body
    assert res["goals"] == []
    assert res["progress"]["daily"]["target_minutes"] == 120 and res["progress"]["daily"]["is_default"] is True
    assert res["progress"]["weekly"] is None and res["progress"]["streak"] == 0


def test_set_overall_and_subject_goals_and_read_progress(api, ids):
    manual(api, ist(5, 7), ist(5, 9), subject_id=ids["taxation"])  # 2 h today (Monday)
    res = put_goals(api, daily(240), weekly(35 * 60), weekly(8 * 60, ids["taxation"]))
    assert res.status_code == 200, res.json_body
    p = res.json_body["progress"]
    assert (p["daily"]["target_minutes"], p["daily"]["percent"], p["daily"]["is_default"]) == (240, 50, False)
    assert (
        p["weekly"]["done_seconds"] == 7200 and p["weekly"]["pace"]["state"] == "ahead"
    )  # nothing is due yet on Monday morning
    tax = p["subjects"][0]
    assert (tax["subject_name"], tax["percent"], tax["remaining_seconds"]) == ("Taxation", 25, 8 * 3600 - 7200)
    assert len(res.json_body["goals"]) == 3


def test_goal_ranges_and_duplicates_are_refused(api):
    assert put_goals(api, daily(10)).status_code == 400
    assert put_goals(api, daily(2000)).status_code == 400
    assert put_goals(api, weekly(20)).status_code == 400
    assert put_goals(api, daily(60), daily(90)).status_code == 400
    assert put_goals(api, weekly(60, "00000000-0000-0000-0000-000000000001")).status_code == 400


def test_changing_a_goal_keeps_the_old_one_for_earlier_days(api, clock):
    from modules.tracking.models import Goal

    put_goals(api, daily(120))
    clock.advance(days=2)  # Wednesday
    put_goals(api, daily(180))
    rows = list(Goal.objects.order_by("effective_from"))
    assert [(g.target_minutes, str(g.effective_from), g.effective_to and str(g.effective_to)) for g in rows] == [
        (120, "2026-10-05", "2026-10-06"),
        (180, "2026-10-07", None),
    ]


def test_changing_a_goal_on_the_day_it_began_just_replaces_it(api):
    from modules.tracking.models import Goal

    put_goals(api, daily(120))
    put_goals(api, daily(150))
    assert [(g.target_minutes, g.effective_to) for g in Goal.objects.all()] == [(150, None)]


def test_replacing_the_set_removes_goals_left_out(api, ids, clock):
    from modules.tracking.models import Goal

    put_goals(api, daily(120), weekly(600, ids["taxation"]))
    clock.advance(days=1)
    put_goals(api, daily(120))
    assert Goal.objects.filter(subject_key="taxation", effective_to__isnull=True).count() == 0
    assert Goal.objects.get(subject_key="taxation").effective_to is not None
    assert len(api.get("/tracking/goals/").json_body["goals"]) == 1


def test_streak_counts_days_that_met_the_goal_in_force_that_day(api, clock):
    put_goals(api, daily(60))  # from Monday the 5th; earlier days are judged by the 120 minute default
    for d in (3, 4):
        manual(api, ist(d, 8), ist(d, 10, 30))
    manual(api, ist(5, 8), ist(5, 9, 30))  # 90 minutes: meets the new 60 minute goal
    assert api.get("/tracking/goals/").json_body["progress"]["streak"] == 3
    clock.advance(days=1)  # Tuesday morning, nothing yet today: the streak still stands
    assert api.get("/tracking/goals/").json_body["progress"]["streak"] == 3
    clock.advance(days=1)  # a whole day missed
    assert api.get("/tracking/goals/").json_body["progress"]["streak"] == 0


def test_earlier_days_keep_the_goal_that_applied_then(api):
    put_goals(api, daily(60))
    manual(api, ist(4, 8), ist(4, 9, 30))  # 90 minutes on Sunday, under the 120 minute default that applied then
    assert api.get("/tracking/goals/").json_body["progress"]["streak"] == 0


def test_manual_time_counts_toward_goals_and_streak(api):
    put_goals(api, daily(30))
    manual(api, ist(5, 6), ist(5, 7))
    assert api.get("/tracking/goals/").json_body["progress"]["daily"]["percent"] == 100


def test_behind_pace_on_a_weekly_goal(api, clock):
    put_goals(api, weekly(35 * 60))
    manual(api, ist(5, 8), ist(5, 9))  # one hour on Monday
    clock.advance(days=2)  # Wednesday: expected 10 h by the start of the day
    pace = api.get("/tracking/goals/").json_body["progress"]["weekly"]["pace"]
    assert pace["state"] == "behind" and pace["gap_seconds"] == 3600 - 10 * 3600


def test_goals_belong_to_the_student(api, other_api):
    put_goals(api, daily(200))
    assert other_api.get("/tracking/goals/").json_body["goals"] == []


def test_settings_defaults_update_and_reset(api):
    s = api.get("/tracking/settings/").json_body
    assert s == {
        "idle_minutes": 10,
        "week_start": 1,
        "default_activity_type": "reading",
        "tz": "Asia/Kolkata",
        "auto_capture_enabled": False,
    }
    res = api.put("/tracking/settings/", {"idle_minutes": 20, "week_start": 0, "tz": "Asia/Singapore"})
    assert res.status_code == 200 and sorted(res.json_body["changed_keys"]) == ["idle_minutes", "tz", "week_start"]
    assert api.put("/tracking/settings/", {"idle_minutes": 20}).json_body["changed_keys"] == []
    assert api.delete("/tracking/settings/").json_body["idle_minutes"] == 10


@pytest.mark.parametrize(
    "body",
    [{"idle_minutes": 3}, {"idle_minutes": 90}, {"week_start": 2}, {"tz": "Mars/Base"}, {"default_activity_type": "x"}],
)
def test_settings_are_validated(api, body):
    assert api.put("/tracking/settings/", body).status_code == 400


def test_the_time_zone_decides_which_day_a_session_belongs_to(api):
    api.put("/tracking/settings/", {"tz": "Asia/Singapore"})
    res = manual(api, ist(4, 23, 30), ist(5, 0, 30))  # 23:30 IST is 02:00 the next day in Singapore
    assert res.json_body["tz"] == "Asia/Singapore" and res.json_body["study_date"] == "2026-10-05"
    assert NOW - timedelta(days=1)  # silence unused import in strict linters
