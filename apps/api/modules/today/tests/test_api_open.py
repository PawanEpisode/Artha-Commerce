"""POST open/ and GET plan/: one plan per student per day, idempotent, and a read never writes (FR-F13-01, 02; PRD 9)."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from modules.coverage import services as coverage_services
from modules.today import registry
from modules.today.models import DayPlan, ProviderConfig, Task
from modules.today.registry import KindSpec

from .conftest import OTHER, USER
from .helpers import candidate, register_fake, register_practice

pytestmark = pytest.mark.django_db


def plan_ids(body):
    return [t["id"] for t in body["tasks"]]


def test_a_new_student_gets_a_plan_of_three_to_eight_tasks_grouped_by_paper(api, enrolled):
    register_practice()
    res = api.post("/today/open/")
    assert res.status_code == 200, res.json_body
    body = res.json_body
    assert body["state"] == "ready" and body["created"] is True and body["generation_no"] == 1
    assert 3 <= len(body["tasks"]) <= 8
    assert body["phase"] == "consolidate" and body["partial"] is False and body["failed_providers"] == []
    assert body["budget_minutes"] == 65  # 35 percent of 180 daily minutes, rounded to 5
    assert body["counts"]["planned"] == body["counts"]["open"] == len(body["tasks"])
    assert body["starter_task_id"] in plan_ids(body)
    assert {t for tile in body["tiles"] for t in tile["tasks"]} == set(plan_ids(body))
    assert body["tomorrow"] is None and len(body["week"]) == 7
    first = body["tasks"][0]
    assert first["state"] == "suggested" and first["link"]["path"].startswith("/app/")
    assert first["why"]["signals"] and first["reason"]


def test_a_second_open_returns_the_same_plan_and_task_ids(api, enrolled):
    first = api.post("/today/open/").json_body
    second = api.post("/today/open/").json_body
    assert second["created"] is False
    assert plan_ids(first) == plan_ids(second) and second["generation_no"] == 1
    assert DayPlan.objects.filter(user_id=USER).count() == 1


def test_open_accepts_client_id_source_and_todays_date(api, enrolled):
    res = api.post("/today/open/", {"client_id": "11111111-1111-4111-8111-111111111111", "source": "reminder"})
    assert res.status_code == 200
    assert api.post("/today/open/", {"source": "bogus"}).status_code == 400


def test_another_date_than_the_students_today_is_refused(api, enrolled):
    tomorrow = (timezone.now() + timedelta(days=2)).date().isoformat()
    res = api.post("/today/open/", {"date": tomorrow})
    assert res.status_code == 400 and res.json_body["error"]["code"] == "invalid_date"
    assert DayPlan.objects.count() == 0


def test_a_student_without_a_course_gets_a_state_and_no_plan(api, scheme):
    res = api.post("/today/open/")
    assert res.status_code == 200 and res.json_body["state"] == "not_enrolled" and res.json_body["plan"] is None
    assert DayPlan.objects.count() == 0


def test_a_student_past_the_exam_gets_post_exam_and_no_plan(api, scheme):
    coverage_services.create_enrollment(
        USER, scheme_id=scheme.id, exam_date=(timezone.now() - timedelta(days=3)).date(), daily_minutes=120
    )
    res = api.post("/today/open/")
    assert res.json_body["state"] == "post_exam" and DayPlan.objects.count() == 0


def test_a_student_without_an_exam_date_still_gets_a_steady_plan(api, scheme):
    coverage_services.create_enrollment(USER, scheme_id=scheme.id)
    body = api.post("/today/open/").json_body
    assert body["phase"] == "steady" and body["days_to_exam"] is None and body["budget_minutes"] == 60


def test_each_student_has_their_own_plan(api, other_api, enrolled):
    coverage_services.create_enrollment(OTHER, scheme_id=enrolled.id, daily_minutes=60)
    mine = api.post("/today/open/").json_body
    theirs = other_api.post("/today/open/").json_body
    assert set(plan_ids(mine)).isdisjoint(plan_ids(theirs))
    assert DayPlan.objects.count() == 2
    assert Task.objects.filter(user_id=OTHER).count() == len(theirs["tasks"])


# ---- GET plan/ never writes ---------------------------------------------------------------------------------------------------


def test_get_plan_before_open_is_404_and_writes_nothing(api, enrolled):
    with CaptureQueriesContext(connection) as queries:
        res = api.get("/today/plan/")
    assert res.status_code == 404 and res.json_body["error"]["code"] == "plan_not_generated"
    assert DayPlan.objects.count() == 0
    assert not [q for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


def test_get_plan_after_open_returns_the_same_plan_and_issues_no_writes(api, enrolled):
    opened = api.post("/today/open/").json_body
    with CaptureQueriesContext(connection) as queries:
        res = api.get("/today/plan/")
    assert res.status_code == 200 and plan_ids(res.json_body) == plan_ids(opened)
    assert "created" not in res.json_body
    assert not [q for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


def test_plan_etag_answers_304_until_something_changes(api, enrolled):
    api.post("/today/open/")
    first = api.get("/today/plan/")
    etag = first["ETag"]
    assert api.get("/today/plan/", HTTP_IF_NONE_MATCH=etag).status_code == 304
    Task.objects.filter(user_id=USER).first().delete()
    assert api.get("/today/plan/", HTTP_IF_NONE_MATCH=etag).status_code == 200


def test_lite_mode_drops_signals_and_the_week(api, enrolled):
    api.post("/today/open/")
    body = api.get("/today/plan/?lite=1").json_body
    assert "week" not in body and "signals" not in body["tasks"][0]["why"]


def test_plan_for_another_date_is_404_not_a_generation(api, enrolled):
    api.post("/today/open/")
    yesterday = (timezone.now() - timedelta(days=1)).date().isoformat()
    assert api.get(f"/today/plan/?date={yesterday}").status_code == 404
    assert DayPlan.objects.count() == 1


# ---- what is stored ----------------------------------------------------------------------------------------------------------


def test_the_plan_row_records_how_it_was_made_without_any_titles(api, enrolled):
    api.post("/today/open/")
    plan = DayPlan.objects.get(user_id=USER)
    assert plan.status == "ready" and plan.generation_no == 1 and plan.first_opened_at and plan.generated_at
    assert plan.provider_status["coverage.syllabus"]["status"] == "ok"
    assert plan.selection_log["v"] == 1 and "dropped" in plan.selection_log
    assert "Study" not in str(plan.selection_log) and "Start" not in str(plan.selection_log)
    assert plan.planned_count == Task.objects.filter(plan=plan).count()
    assert plan.planned_minutes == sum(Task.objects.filter(plan=plan).values_list("est_minutes", flat=True))
    assert plan.context_hash and len(plan.context_hash) == 64


def test_tasks_keep_stable_subject_and_chapter_keys(api, enrolled):
    api.post("/today/open/")
    task = Task.objects.filter(user_id=USER, chapter__isnull=False).first()
    assert task.subject_key and task.chapter_key and task.provider.startswith("coverage.")


# ---- providers failing, switches, settings -----------------------------------------------------------------------------------


def test_a_failing_provider_marks_the_plan_partial_and_the_rest_still_arrives(api, enrolled):
    def boom(request):
        raise RuntimeError("down")

    register_fake("fake.boom", boom, kinds=[KindSpec("boom_k", "practice", "mcq", "x", 10)])
    body = api.post("/today/open/").json_body
    assert body["partial"] is True and body["failed_providers"] == ["fake.boom"]
    assert body["tasks"]


def test_a_provider_candidate_with_a_bad_link_is_dropped_and_counted(api, enrolled):
    register_fake("fake.bad", [candidate("bad", link=registry.DeepLink("https://evil.example"))])
    body = api.post("/today/open/").json_body
    assert all(t["title"] != "Task bad" for t in body["tasks"])
    assert DayPlan.objects.get(user_id=USER).selection_log["dropped"]["invalid_link"] == 1


def test_a_candidate_of_an_unknown_kind_is_counted_invalid_and_never_fatal(api, enrolled):
    register_fake("fake.odd", [candidate("x", kind="not_declared")])
    assert api.post("/today/open/").status_code == 200
    assert DayPlan.objects.get(user_id=USER).selection_log["dropped"]["invalid"] == 1


def test_a_backlog_is_summarised_with_how_many_are_scheduled(api, enrolled):
    from modules.coverage.models import ChapterProgress

    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=(timezone.now() - timedelta(days=2)).date(), revision_count=1
    )
    ProviderConfig.objects.create(provider="coverage.revision", max_candidates=1)  # the operator caps what it may offer
    body = api.post("/today/open/").json_body
    [notice] = body["backlog"]
    assert notice["kind"] == "revision" and notice["link"]["path"] == "/app/revision" and notice["label"]
    assert notice["count"] == ChapterProgress.objects.filter(user_id=USER).count() - 1 and notice["scheduled"] == 1


def test_a_draft_plan_made_by_an_own_task_is_upgraded_not_duplicated(api, enrolled):
    today = timezone.localdate()
    draft = DayPlan.objects.create(user_id=USER, local_date=today, tz="UTC", status="draft", generation_no=0)
    Task.objects.create(
        user_id=USER, plan=draft, local_date=today, origin="user", kind="custom", slot="custom",
        dedupe_key="user:1", title="Call the CA coaching centre", est_minutes=5, position=0,
    )  # fmt: skip
    body = api.post("/today/open/").json_body
    assert body["generation_no"] == 1 and DayPlan.objects.count() == 1
    titles = [t["title"] for t in body["tasks"]]
    assert "Call the CA coaching centre" in titles and titles[-1] == "Call the CA coaching centre"
