"""preview/, history/, settings/ and the access matrix for every Today endpoint (401, 403, 404)."""

import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from modules.today import urls as today_urls
from modules.today.models import DayPlan, Task, TodaySettings
from modules.today.views import TodayView

from .conftest import USER, Api
from .helpers import local_today, register_practice

pytestmark = pytest.mark.django_db


def day(offset):
    return (local_today() + timedelta(days=offset)).isoformat()


def writes(queries):
    return [q for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


# ---- access matrix (built from the URL patterns, so a new endpoint is covered the day it is added) ---------------------------


def requests_for_every_endpoint():
    seen = []
    for pattern in today_urls.urlpatterns:
        kwargs = {name: uuid.uuid4() for name in pattern.pattern.converters}
        view_class = pattern.callback.view_class
        assert issubclass(view_class, TodayView), f"{pattern.name} must extend TodayView"
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view_class, method):
                seen.append((method, reverse(pattern.name, kwargs=kwargs).removeprefix("/api/v1"), pattern.name))
    assert len(seen) >= 6  # guards against the discovery silently finding nothing
    return seen


def test_every_endpoint_answers_401_without_a_token(db):
    anonymous = Api("")
    anonymous.c.defaults.pop("HTTP_AUTHORIZATION", None)
    for method, path, name in requests_for_every_endpoint():
        res = anonymous._send(method, path, {} if method != "get" else None)
        assert res.status_code == 401, f"{method.upper()} {name}"


def test_every_endpoint_answers_401_with_a_bad_token(db):
    bad = Api("not-a-token")
    for method, path, name in requests_for_every_endpoint():
        assert bad._send(method, path, {} if method != "get" else None).status_code == 401, name


def test_every_endpoint_answers_403_feature_disabled_when_the_flag_is_off(api, flag):
    flag(False)
    for method, path, name in requests_for_every_endpoint():
        res = api._send(method, path, {} if method != "get" else None)
        assert res.status_code == 403, f"{method.upper()} {name}"
        assert res.json_body["error"]["code"] == "feature_disabled", name


def test_the_flag_fails_closed_when_posthog_cannot_answer(api, settings):
    settings.POSTHOG_API_KEY = ""  # no key: every flag lookup is unknown
    from core import feature_flags

    feature_flags.clear_flag_cache()
    feature_flags._client = None
    assert api.post("/today/open/").status_code == 403


def test_no_plan_for_a_student_is_a_404_and_other_students_plans_are_never_found(api, other_api, enrolled):
    api.post("/today/open/")
    res = other_api.get("/today/plan/")
    assert res.status_code == 404 and res.json_body["error"]["code"] == "plan_not_generated"


def test_unsupported_methods_are_405(api):
    assert api.post("/today/plan/").status_code == 405
    assert api.get("/today/open/").status_code == 405
    assert api.post("/today/history/").status_code == 405


# ---- preview ----------------------------------------------------------------------------------------------------------------


def test_preview_shows_up_to_four_tasks_and_stores_nothing(api, enrolled):
    register_practice()
    with CaptureQueriesContext(connection) as queries:
        res = api.get(f"/today/preview/?date={day(1)}")
    assert res.status_code == 200, res.json_body
    body = res.json_body
    assert body["date"] == day(1) and 1 <= body["count"] <= 4 and len(body["tasks"]) == body["count"]
    assert body["minutes"] == sum(t["est_minutes"] for t in body["tasks"])
    assert DayPlan.objects.count() == 0 and Task.objects.count() == 0
    assert not writes(queries)


def test_preview_includes_the_students_own_tasks_for_that_day(api, enrolled):
    target = local_today() + timedelta(days=3)
    plan = DayPlan.objects.create(user_id=USER, local_date=target, tz="Asia/Kolkata", status="draft", generation_no=0)
    Task.objects.create(
        user_id=USER, plan=plan, local_date=target, origin="user", kind="custom", slot="custom",
        dedupe_key="user:7", title="Mock paper review", est_minutes=30, position=0,
    )  # fmt: skip
    body = api.get(f"/today/preview/?date={target.isoformat()}").json_body
    assert [t["title"] for t in body["own_tasks"]] == ["Mock paper review"]


@pytest.mark.parametrize("offset", [0, -1, 15, 40])
def test_preview_dates_outside_tomorrow_to_two_weeks_are_refused(api, enrolled, offset):
    res = api.get(f"/today/preview/?date={day(offset)}")
    assert res.status_code == 400 and res.json_body["error"]["code"] == "invalid_date"


def test_preview_needs_a_valid_date(api, enrolled):
    assert api.get("/today/preview/").status_code == 400
    assert api.get("/today/preview/?date=tomorrow").status_code == 400


def test_preview_for_a_student_without_a_course_is_empty_not_an_error(api, scheme):
    body = api.get(f"/today/preview/?date={day(1)}").json_body
    assert body["count"] == 0 and body["tasks"] == []


# ---- history ----------------------------------------------------------------------------------------------------------------


def test_history_lists_days_that_had_a_plan(api, enrolled):
    api.post("/today/open/")
    body = api.get("/today/history/").json_body
    [today] = body["days"]
    assert today["date"] == day(0) and today["outcome"] == "none" and today["planned_count"] >= 1
    assert body["from"] == day(-6) and body["to"] == day(0)


def test_history_empty_for_a_new_student_and_never_writes(api, enrolled):
    with CaptureQueriesContext(connection) as queries:
        body = api.get("/today/history/").json_body
    assert body["days"] == [] and not writes(queries)


def test_history_range_is_limited_to_92_days(api, enrolled):
    assert api.get(f"/today/history/?from={day(-91)}&to={day(0)}").status_code == 200
    too_long = api.get(f"/today/history/?from={day(-92)}&to={day(0)}")
    assert too_long.status_code == 400 and too_long.json_body["error"]["code"] == "invalid_date"
    assert api.get(f"/today/history/?from={day(0)}&to={day(-3)}").status_code == 400
    assert api.get("/today/history/?from=yesterday").status_code == 400


def test_history_counts_done_and_skipped(api, enrolled):
    api.post("/today/open/")
    plan = DayPlan.objects.get(user_id=USER)
    DayPlan.objects.filter(pk=plan.pk).update(planned_count=4, done_count=3, skipped_count=1, open_count=0)
    [row] = api.get("/today/history/").json_body["days"]
    assert row["outcome"] == "all" and row["done_count"] == 3


# ---- settings ---------------------------------------------------------------------------------------------------------------


def test_settings_default_without_creating_a_row(api, enrolled):
    with CaptureQueriesContext(connection) as queries:
        body = api.get("/today/settings/").json_body
    assert body["minutes_per_day"] is None and body["focus_papers"] is None and body["lite_mode"] == "auto"
    assert body["show_tomorrow"] is True and body["celebrate"] is True and body["disabled_kinds"] == []
    assert TodaySettings.objects.count() == 0 and not writes(queries)


def test_settings_put_saves_only_what_is_sent(api, enrolled):
    res = api.put("/today/settings/", {"minutes_per_day": 90, "celebrate": False})
    assert res.status_code == 200 and res.json_body["minutes_per_day"] == 90 and res.json_body["celebrate"] is False
    again = api.put("/today/settings/", {"focus_papers": 4}).json_body
    assert again["minutes_per_day"] == 90 and again["focus_papers"] == 4
    assert api.put("/today/settings/", {"minutes_per_day": None}).json_body["minutes_per_day"] is None
    assert TodaySettings.objects.get(pk=USER).focus_papers == 4


@pytest.mark.parametrize(
    "body",
    [
        {"minutes_per_day": 14},
        {"minutes_per_day": 241},
        {"focus_papers": 0},
        {"focus_papers": 5},
        {"lite_mode": "max"},
        {"show_tomorrow": "sometimes"},
        {"disabled_kinds": ["no_such_kind"]},
        {"disabled_kinds": [f"k{n}" for n in range(21)]},
    ],
)
def test_settings_validation(api, enrolled, body):
    res = api.put("/today/settings/", body)
    assert res.status_code == 400 and res.json_body["error"]["code"] == "invalid"
    assert TodaySettings.objects.count() == 0


def test_a_students_settings_are_their_own(api, other_api, enrolled):
    api.put("/today/settings/", {"minutes_per_day": 120})
    assert other_api.get("/today/settings/").json_body["minutes_per_day"] is None


def test_minutes_per_day_sets_the_next_plans_budget(api, enrolled):
    api.put("/today/settings/", {"minutes_per_day": 90})
    body = api.post("/today/open/").json_body
    assert body["budget_minutes"] == 90
    assert DayPlan.objects.get(user_id=USER).budget_source == "setting"


def test_a_hidden_kind_is_not_offered(api, enrolled):
    api.put("/today/settings/", {"disabled_kinds": ["next_chapter", "next_topic"]})
    body = api.post("/today/open/").json_body
    assert all(t["kind"] not in ("next_chapter", "next_topic") for t in body["tasks"])
    assert DayPlan.objects.get(user_id=USER).selection_log["dropped"]["hidden_kind"] >= 1


def test_lite_mode_setting_on_drops_signals_without_a_query_parameter(api, enrolled):
    api.put("/today/settings/", {"lite_mode": "on"})
    api.post("/today/open/")
    body = api.get("/today/plan/").json_body
    assert "week" not in body and "signals" not in body["tasks"][0]["why"]


def test_throttle_scopes_exist_with_the_documented_rates(settings):
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert (rates["today_read"], rates["today_write"], rates["today_regen"]) == ("120/min", "120/min", "6/day")
