"""W8: the planner endpoints (`today/planner/...`), their flag, errors and what a re-plan stores."""

import uuid
from datetime import timedelta

import pytest

from modules.coverage import services as coverage_services
from modules.coverage.models import ChapterProgress, Enrollment
from modules.syllabus.models import ExamTerm
from modules.today import planner_hooks, planner_services
from modules.today.models import Milestone, ReplanEvent, StudyPlan

from .conftest import USER
from .helpers import local_today

pytestmark = pytest.mark.django_db


def short_course(days=20, daily=30):
    """An exam in `days` days at `daily` minutes a day: 240 minutes of reading cannot fit, so the plan is `at_risk`."""
    Enrollment.objects.filter(user_id=USER).update(exam_date=local_today() + timedelta(days=days), daily_minutes=daily)


@pytest.fixture
def made(api, enrolled):
    res = api.post("/today/planner/")
    assert res.status_code == 201, res.json_body
    return api, res.json_body


@pytest.fixture
def short(api, enrolled):
    short_course()
    res = api.post("/today/planner/")
    assert res.status_code == 201, res.json_body
    return api, res.json_body


# ---- flag and auth ----------------------------------------------------------------------------------------------------------


def test_the_planner_needs_its_own_flag(api, enrolled, flag):
    flag(True, planner=False)
    for res in (api.get("/today/planner/"), api.post("/today/planner/"), api.get("/today/planner/events/")):
        assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"
    assert api.get("/today/plan/").status_code == 404  # Today itself is on and unaffected


def test_the_planner_does_not_need_the_today_flag(api, enrolled, flag):
    flag(False, planner=True)
    assert api.post("/today/planner/").status_code == 201


def test_no_token_is_401(client):
    assert client.get("/api/v1/today/planner/").status_code == 401


# ---- make the plan ----------------------------------------------------------------------------------------------------------


def test_get_without_a_plan_is_404_and_writes_nothing(api, enrolled):
    res = api.get("/today/planner/")
    assert res.status_code == 404 and res.json_body["error"]["code"] == "study_plan_not_found"
    assert not StudyPlan.objects.exists()


def test_the_first_post_makes_the_plan_and_the_second_returns_it(made):
    api, body = made
    assert body["created"] is True and body["health"] == "on_track" and body["daily_minutes"] == 180
    kinds = {(m["subject_key"], m["kind"]) for m in body["milestones"]}
    assert ("taxation", "finish_reading") in kinds and ("", "exam_week") in kinds
    assert body["reading_deadline"] and body["pending"] is None
    again = api.post("/today/planner/")
    assert again.status_code == 200 and again.json_body["created"] is False and again.json_body["id"] == body["id"]
    assert StudyPlan.objects.count() == 1 and Milestone.objects.filter(plan_id=body["id"]).count() == 7
    assert api.get("/today/planner/").json_body["id"] == body["id"]


def test_the_deadline_is_frozen_at_creation(made):
    _, body = made
    plan = StudyPlan.objects.get()
    assert plan.reading_deadline.isoformat() == body["reading_deadline"]
    assert plan.shortfall_minutes == max(0, plan.remaining_minutes - plan.capacity_minutes)


def test_a_student_without_a_course_is_told_what_is_missing(api):
    res = api.post("/today/planner/")
    assert res.status_code == 422
    assert res.json_body["error"]["code"] == "planner_not_ready"
    assert res.json_body["error"]["details"]["reason"] == "not_enrolled"


def test_an_exam_date_that_has_passed_is_not_ready(api, enrolled):
    Enrollment.objects.filter(user_id=USER).update(exam_date=local_today())
    assert api.post("/today/planner/").json_body["error"]["details"]["reason"] == "post_exam"


def test_daily_minutes_are_validated(api, enrolled):
    for bad in (5, 5000, "x"):
        res = api.post("/today/planner/", {"daily_minutes": bad})
        assert res.status_code == 400 and res.json_body["error"]["code"] == "invalid"
    assert not StudyPlan.objects.exists()


def test_another_student_never_sees_my_plan(made, other_api):
    assert other_api.get("/today/planner/").status_code == 404
    assert other_api.get("/today/planner/events/").status_code == 404


def test_new_daily_minutes_re_plan_the_plan(made):
    api, body = made
    res = api.post("/today/planner/", {"daily_minutes": 90})
    assert res.status_code == 200 and res.json_body["daily_minutes"] == 90 and res.json_body["created"] is False
    assert res.json_body["replan_no"] == body["replan_no"] + 1
    assert ReplanEvent.objects.get().trigger == "manual"


# ---- re-plan and the options -----------------------------------------------------------------------------------------------


def test_a_manual_replan_that_fits_applies_and_records(made):
    api, _ = made
    res = api.post("/today/planner/replan/")
    assert res.status_code == 200
    event = res.json_body["replan"]
    assert event["trigger"] == "manual" and event["options"] == [] and res.json_body["pending"] is None
    assert len(api.get("/today/planner/events/").json_body["events"]) == 1


def test_a_replan_with_a_shortfall_proposes_and_changes_nothing(short):
    api, body = short
    assert body["health"] == "at_risk" and body["shortfall_minutes"] > 0
    before = {m["id"]: (m["target_date"], m["status"]) for m in body["milestones"]}
    res = api.post("/today/planner/replan/").json_body
    assert res["pending"] and res["pending"]["id"] == res["replan"]["id"]
    assert {o["option"] for o in res["pending"]["options"]} == {"more_time", "skim_low_weight", "next_attempt"}
    assert {m["id"]: (m["target_date"], m["status"]) for m in res["milestones"]} == before


def test_choosing_more_time_applies_it_once(short):
    api, _ = short
    event = api.post("/today/planner/replan/").json_body["replan"]
    res = api.post("/today/planner/options/", {"event_id": event["id"], "option": "more_time"})
    assert res.status_code == 200, res.json_body
    assert res.json_body["health"] == "on_track" and res.json_body["shortfall_minutes"] == 0
    assert res.json_body["daily_minutes"] > 30 and res.json_body["pending"] is None
    assert res.json_body["replan"]["option_chosen"] == "more_time"
    again = api.post("/today/planner/options/", {"event_id": event["id"], "option": "more_time"})
    assert again.status_code == 409 and again.json_body["error"]["code"] == "option_expired"


def test_choosing_to_skim_stores_the_skim_and_keeps_the_daily_minutes(api, enrolled):
    short_course(daily=60)  # a small gap: skimming the lightest chapters closes it
    api.post("/today/planner/")
    event = api.post("/today/planner/replan/").json_body["replan"]
    skim = next(o for o in event["options"] if o["option"] == "skim_low_weight")
    assert skim["feasible"]
    res = api.post("/today/planner/options/", {"event_id": event["id"], "option": "skim_low_weight"}).json_body
    assert res["daily_minutes"] == 60 and res["shortfall_minutes"] == 0
    assert StudyPlan.objects.get().params["skimmed"]


def test_choosing_none_keeps_the_plan(short):
    api, body = short
    event = api.post("/today/planner/replan/").json_body["replan"]
    res = api.post("/today/planner/options/", {"event_id": event["id"], "option": "none"}).json_body
    assert res["daily_minutes"] == 30 and res["health"] == "at_risk" and res["pending"] is None
    assert ReplanEvent.objects.get(pk=event["id"]).option_chosen == "none"


def test_an_option_that_was_not_offered_is_refused(made):
    api, _ = made
    event = api.post("/today/planner/replan/").json_body["replan"]  # the plan fits: there are no options
    res = api.post("/today/planner/options/", {"event_id": event["id"], "option": "more_time"})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "option_not_available"
    assert ReplanEvent.objects.get(pk=event["id"]).option_chosen is None
    assert api.post("/today/planner/options/", {"event_id": event["id"], "option": "bogus"}).status_code == 400


def test_options_of_an_old_replan_expire(short):
    api, _ = short
    old = api.post("/today/planner/replan/").json_body["replan"]
    api.post("/today/planner/replan/")
    res = api.post("/today/planner/options/", {"event_id": old["id"], "option": "more_time"})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "option_expired"


def test_an_unknown_or_foreign_event_is_404(short, other_api):
    api, _ = short
    event = api.post("/today/planner/replan/").json_body["replan"]
    assert api.post("/today/planner/options/", {"event_id": str(uuid.uuid4()), "option": "none"}).status_code == 404
    res = other_api.post("/today/planner/options/", {"event_id": event["id"], "option": "none"})
    assert res.status_code == 404 and res.json_body["error"]["code"] == "replan_not_found"


def test_the_next_attempt_moves_the_exam_date_on_the_enrolment(short):
    api, _ = short
    enrollment = Enrollment.objects.get(user_id=USER)
    later = (
        ExamTerm.objects.filter(level=enrollment.scheme.level, exam_start__gt=enrollment.exam_date)
        .order_by("exam_start")
        .values_list("exam_start", flat=True)
        .first()
    )
    assert later is not None
    event = api.post("/today/planner/replan/").json_body["replan"]
    attempt = next(o for o in event["options"] if o["option"] == "next_attempt")
    assert attempt["feasible"] and attempt["exam_date"] == later.isoformat()
    res = api.post("/today/planner/options/", {"event_id": event["id"], "option": "next_attempt"}).json_body
    assert res["exam_date"] == later.isoformat() and res["health"] == "on_track"
    enrollment.refresh_from_db()
    assert enrollment.exam_date == later
    plan = StudyPlan.objects.get()
    assert plan.reading_deadline <= later and plan.reading_deadline > local_today() + timedelta(days=20)
    assert plan.exam_date == later


def test_the_replan_endpoint_is_throttled_per_day(made, settings):
    api, _ = made
    for _n in range(20):
        assert api.post("/today/planner/replan/").status_code == 200
    assert api.post("/today/planner/replan/").status_code == 429


def test_events_are_newest_first_and_limited(made):
    api, _ = made
    for _n in range(3):
        api.post("/today/planner/replan/")
    events = api.get("/today/planner/events/?limit=2").json_body["events"]
    assert len(events) == 2 and events[0]["created_at"] >= events[1]["created_at"]
    assert api.get("/today/planner/events/?limit=0").status_code == 400


# ---- progress and the course changing under the plan -----------------------------------------------------------------------


def read_paper(key):
    for progress in ChapterProgress.objects.filter(user_id=USER, chapter__subject__key=key):
        progress.read_pct = 100
        progress.save()


def test_finishing_a_papers_reading_marks_its_milestone_done_that_day(made):
    api, _ = made
    read_paper("corporate-laws")
    assert planner_hooks.on_coverage_event(type="topic_done", user_id=str(USER)) is None
    done = Milestone.objects.get(subject_key="corporate-laws", kind="finish_reading")
    assert done.status == "done" and done.done_at and done.target_date == local_today() and done.remaining_minutes == 0
    assert Milestone.objects.get(subject_key="taxation", kind="finish_reading").status != "done"
    assert planner_services.mark_reading_done(USER) == 0  # nothing new the second time


def test_a_student_without_a_plan_costs_nothing(api, enrolled):
    assert planner_services.mark_reading_done(USER) == 0
    assert planner_services.sync_enrollment(USER) is None


def test_a_new_exam_date_re_plans_with_the_exam_date_trigger(made):
    api, body = made
    new = local_today() + timedelta(days=100)
    coverage_services.update_enrollment(Enrollment.objects.get(user_id=USER), data={"exam_date": new})
    planner_hooks.on_course_changed(user_id=str(USER))
    plan = StudyPlan.objects.get()
    assert plan.exam_date == new and plan.reading_deadline.isoformat() != body["reading_deadline"]
    assert ReplanEvent.objects.get().trigger == "exam_date"
    planner_hooks.on_course_changed(user_id=str(USER))
    assert ReplanEvent.objects.count() == 1  # the plan already follows the course: nothing to do


def test_another_scheme_starts_a_new_plan_and_supersedes_the_old(made):
    api, body = made
    from modules.syllabus.tests.helpers import switch_scheme

    other = switch_scheme(Enrollment.objects.get(user_id=USER).scheme)
    coverage_services.switch_scheme(USER, Enrollment.objects.get(user_id=USER, status="active"), other.id)
    planner_hooks.on_course_changed(user_id=str(USER))
    old, new = StudyPlan.objects.get(pk=body["id"]), StudyPlan.objects.get(status="active")
    assert old.status == "superseded" and new.pk != old.pk and new.scheme_id == other.id
    assert ReplanEvent.objects.get(plan=new).trigger == "scheme_switch"
    assert api.get("/today/planner/").json_body["id"] == str(new.pk)
