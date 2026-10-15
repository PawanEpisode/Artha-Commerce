"""The student's own tasks: add, edit, delete, undo, quotas, draft plans, snooze to another day (PRD FR-F13-30)."""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.coverage import selectors as coverage_selectors
from modules.today.models import DayPlan, Task

from .conftest import USER
from .helpers import cid, local_today, register_practice
from .test_task_actions import reference_counts, stored_counts

pytestmark = pytest.mark.django_db


def add(api, **over):
    body = {"client_id": cid(), "title": "Call the coaching centre", "est_minutes": 10}
    body.update(over)
    return api.post("/today/tasks/", body)


def scope():
    state = coverage_selectors.study_state(USER, coverage_selectors.get_active_enrollment(USER), "Asia/Kolkata")
    paper = state.subjects[0]
    return paper, paper.chapters[0]


# ---- add --------------------------------------------------------------------------------------------------------------------


def test_adding_a_task_before_the_plan_exists_makes_a_draft_that_open_upgrades(api, enrolled):
    res = add(api)
    assert res.status_code == 201
    task = res.json_body["task"]
    assert task["origin"] == "user" and task["state"] == "suggested" and task["reason_code"] == "custom"
    plan = DayPlan.objects.get(user_id=USER, local_date=local_today())
    assert plan.status == "draft" and plan.planned_count == 1
    assert api.get("/today/plan/").status_code == 404  # a draft is not a generated plan
    opened = api.post("/today/open/").json_body
    assert opened["generation_no"] == 1 and opened["created"] is True
    assert task["id"] in [t["id"] for t in opened["tasks"]]
    assert DayPlan.objects.filter(user_id=USER).count() == 1


def test_adding_to_an_existing_plan_appends_and_recounts(api, enrolled):
    register_practice()
    before = api.post("/today/open/").json_body
    body = add(api, est_minutes=25).json_body
    assert body["counts"]["planned"] == before["counts"]["planned"] + 1
    assert body["task"]["est_minutes"] == 25
    plan = DayPlan.objects.get(user_id=USER, local_date=local_today())
    assert stored_counts(plan.id) == reference_counts(plan.id)
    assert plan.planned_minutes == before["planned_minutes"] + 25


def test_a_retry_with_the_same_client_id_returns_the_original(api, enrolled):
    c = cid()
    first = add(api, client_id=c)
    again = add(api, client_id=c, title="A different title")
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json_body["task"]["id"] == first.json_body["task"]["id"]
    assert Task.objects.filter(user_id=USER, origin="user").count() == 1


def test_a_chapter_alone_fills_in_its_paper(api, enrolled):
    paper, chapter = scope()
    task = add(api, chapter_id=str(chapter.chapter_id)).json_body["task"]
    assert task["subject_id"] == str(paper.subject_id) and task["chapter_id"] == str(chapter.chapter_id)


def test_a_paper_and_chapter_that_do_not_match_are_refused(api, enrolled):
    state = coverage_selectors.study_state(USER, coverage_selectors.get_active_enrollment(USER), "Asia/Kolkata")
    first, second = state.subjects[0], state.subjects[1]
    res = add(api, subject_id=str(first.subject_id), chapter_id=str(second.chapters[0].chapter_id))
    assert res.status_code == 400 and res.json_body["error"]["code"] == "invalid_scope"


def test_an_unknown_paper_is_refused(api, enrolled):
    res = add(api, subject_id=str(uuid.uuid4()))
    assert res.status_code == 400 and res.json_body["error"]["code"] == "invalid_scope"


def test_a_paper_without_a_course_is_refused(api, scheme):
    res = add(api, subject_id=str(uuid.uuid4()))
    assert res.status_code == 400 and res.json_body["error"]["code"] == "invalid_scope"


@pytest.mark.parametrize("offset,ok", [(-1, False), (0, True), (30, True), (31, False)])
def test_the_date_window_is_today_to_thirty_days(api, enrolled, offset, ok):
    res = add(api, date=(local_today() + timedelta(days=offset)).isoformat())
    assert (res.status_code == 201) is ok
    if not ok:
        assert res.json_body["error"]["code"] == "invalid_date"


@pytest.mark.parametrize(
    "bad", [{"title": ""}, {"title": "x" * 121}, {"est_minutes": 0}, {"est_minutes": 181}, {"title": "   "}]
)
def test_bad_input_is_a_400(api, enrolled, bad):
    assert add(api, **bad).status_code == 400


def test_a_future_day_gets_a_draft_and_shows_in_preview(api, enrolled):
    day = local_today() + timedelta(days=3)
    add(api, date=day.isoformat(), title="Mock paper review")
    assert DayPlan.objects.get(user_id=USER, local_date=day).status == "draft"
    preview = api.get(f"/today/preview/?date={day.isoformat()}").json_body
    assert [t["title"] for t in preview["own_tasks"]] == ["Mock paper review"]


def test_the_twenty_first_task_of_a_day_is_429(api, enrolled):
    for n in range(20):
        assert add(api, title=f"Task {n}").status_code == 201
    res = add(api, title="One too many")
    assert res.status_code == 429 and res.json_body["error"]["code"] == "quota_exceeded"
    assert res.json_body["error"]["details"] == {"kind": "own_tasks_per_day", "used": 20, "limit": 20}
    assert (
        add(api, date=(local_today() + timedelta(days=1)).isoformat()).status_code == 201
    )  # another day is another quota


def test_deleted_tasks_do_not_count_toward_the_daily_quota(api, enrolled):
    ids = [add(api, title=f"T{n}").json_body["task"]["id"] for n in range(20)]
    assert api.delete(f"/today/tasks/{ids[0]}/").status_code == 200
    assert add(api).status_code == 201


def test_two_hundred_open_tasks_for_later_days_is_the_limit(api, enrolled):
    base = local_today() + timedelta(days=2)
    plan = DayPlan.objects.create(user_id=USER, local_date=base, tz="Asia/Kolkata", status="draft", generation_no=0)
    Task.objects.bulk_create(
        Task(
            user_id=USER, plan=plan, local_date=base, origin="user", kind="own_task", slot="custom", dedupe_key=f"own:{n}",
            title="t", est_minutes=5, position=n,
        )
        for n in range(200)
    )  # fmt: skip
    res = add(api, date=(local_today() + timedelta(days=5)).isoformat())
    assert res.status_code == 429 and res.json_body["error"]["details"]["kind"] == "own_tasks_future"
    assert add(api).status_code == 201  # today is not "later"


# ---- edit -------------------------------------------------------------------------------------------------------------------


def test_edit_changes_the_fields_and_bumps_the_version(api, enrolled):
    task = add(api).json_body["task"]
    res = api.patch(
        f"/today/tasks/{task['id']}/", {"version": task["version"], "title": "  New   title ", "est_minutes": 45}
    )
    body = res.json_body
    assert res.status_code == 200 and body["task"]["title"] == "New title" and body["task"]["est_minutes"] == 45
    assert body["task"]["version"] == task["version"] + 1
    plan = DayPlan.objects.get(user_id=USER, local_date=local_today())
    assert plan.planned_minutes == 45


def test_edit_with_a_stale_version_is_a_conflict_that_returns_the_task(api, enrolled):
    task = add(api).json_body["task"]
    api.patch(f"/today/tasks/{task['id']}/", {"version": task["version"], "title": "First"})
    res = api.patch(f"/today/tasks/{task['id']}/", {"version": task["version"], "title": "Second"})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "state_conflict"
    assert res.json_body["error"]["details"]["task"]["title"] == "First"


def test_edit_needs_a_field(api, enrolled):
    task = add(api).json_body["task"]
    assert api.patch(f"/today/tasks/{task['id']}/", {"version": task["version"]}).status_code == 400


def test_edit_can_move_the_task_to_another_day(api, enrolled):
    task = add(api).json_body["task"]
    day = local_today() + timedelta(days=4)
    res = api.patch(f"/today/tasks/{task['id']}/", {"version": task["version"], "date": day.isoformat()})
    assert res.status_code == 200
    row = Task.objects.get(pk=task["id"])
    assert row.local_date == day and row.plan.local_date == day
    today_plan = DayPlan.objects.get(user_id=USER, local_date=local_today())
    assert today_plan.planned_count == 0 and stored_counts(row.plan_id) == reference_counts(row.plan_id)


def test_edit_can_set_and_clear_the_paper(api, enrolled):
    paper, chapter = scope()
    task = add(api).json_body["task"]
    set_ = api.patch(
        f"/today/tasks/{task['id']}/", {"version": task["version"], "chapter_id": str(chapter.chapter_id)}
    ).json_body
    assert set_["task"]["subject_id"] == str(paper.subject_id)
    cleared = api.patch(
        f"/today/tasks/{task['id']}/", {"version": set_["task"]["version"], "subject_id": None, "chapter_id": None}
    ).json_body
    assert cleared["task"]["subject_id"] is None and cleared["task"]["chapter_id"] is None


def test_suggested_tasks_cannot_be_edited_or_deleted(api, enrolled):
    register_practice()
    plan = api.post("/today/open/").json_body
    task = next(t for t in plan["tasks"] if t["origin"] == "provider")
    patch = api.patch(f"/today/tasks/{task['id']}/", {"version": task["version"], "title": "Mine now"})
    delete = api.delete(f"/today/tasks/{task['id']}/")
    for res in (patch, delete):
        assert res.status_code == 403 and res.json_body["error"]["code"] == "provider_task_readonly"
    assert Task.objects.get(pk=task["id"]).title == task["title"]


def test_another_students_task_cannot_be_edited_or_deleted(api, other_api, enrolled):
    task = add(api).json_body["task"]
    assert other_api.patch(f"/today/tasks/{task['id']}/", {"version": 1, "title": "x"}).status_code == 404
    assert other_api.delete(f"/today/tasks/{task['id']}/").status_code == 404


# ---- delete and undo --------------------------------------------------------------------------------------------------------


def test_delete_is_soft_hides_the_task_and_recounts(api, enrolled):
    task = add(api).json_body["task"]
    res = api.delete(f"/today/tasks/{task['id']}/")
    body = res.json_body
    assert res.status_code == 200 and body["counts"]["planned"] == 0 and body["undo_until"]
    row = Task.objects.get(pk=task["id"])
    assert row.deleted_at is not None
    plan_tasks = api.post("/today/open/").json_body["tasks"]
    assert task["id"] not in [t["id"] for t in plan_tasks]


def test_undo_a_delete_within_the_window(api, enrolled):
    task = add(api).json_body["task"]
    api.delete(f"/today/tasks/{task['id']}/")
    res = api.post(f"/today/tasks/{task['id']}/undo/", {"client_id": cid(), "from_state": "deleted"})
    assert res.status_code == 200 and res.json_body["counts"]["planned"] == 1
    assert Task.objects.get(pk=task["id"]).deleted_at is None


def test_undo_a_delete_after_the_window_is_410(api, enrolled):
    task = add(api).json_body["task"]
    api.delete(f"/today/tasks/{task['id']}/")
    Task.objects.filter(pk=task["id"]).update(deleted_at=timezone.now() - timedelta(seconds=90))
    res = api.post(f"/today/tasks/{task['id']}/undo/", {"client_id": cid(), "from_state": "deleted"})
    assert res.status_code == 410


def test_a_deleted_task_answers_404_to_other_actions(api, enrolled):
    task = add(api).json_body["task"]
    api.delete(f"/today/tasks/{task['id']}/")
    assert api.post(f"/today/tasks/{task['id']}/complete/", {"client_id": cid()}).status_code == 404


# ---- complete and snooze an own task ----------------------------------------------------------------------------------------


def test_an_own_task_can_be_completed_and_undone(api, enrolled):
    task = add(api).json_body["task"]
    done = api.post(f"/today/tasks/{task['id']}/complete/", {"client_id": cid()}).json_body
    assert done["task"]["state"] == "done" and done["counts"]["done"] == 1
    back = api.post(f"/today/tasks/{task['id']}/undo/", {"client_id": cid(), "from_state": "done"}).json_body
    assert back["task"]["state"] == "suggested"


def test_snoozing_an_own_task_moves_it_to_that_day_and_it_wakes_when_the_day_opens(api, enrolled):
    task = add(api).json_body["task"]
    res = api.post(f"/today/tasks/{task['id']}/snooze/", {"client_id": cid(), "until": "tomorrow"})
    assert res.status_code == 200 and res.json_body["task"]["state"] == "snoozed"
    tomorrow = local_today() + timedelta(days=1)
    row = Task.objects.get(pk=task["id"])
    assert row.local_date == tomorrow and row.plan.local_date == tomorrow and row.snoozed_until == tomorrow
    today_plan = DayPlan.objects.get(user_id=USER, local_date=local_today())
    tomorrow_plan = DayPlan.objects.get(user_id=USER, local_date=tomorrow)
    assert today_plan.planned_count == 0 and tomorrow_plan.snoozed_count == 1 and tomorrow_plan.planned_count == 0
    # the day arrives: the plan is generated and the task is a suggestion again
    tomorrow_plan.status = "ready"
    tomorrow_plan.generation_no = 1
    tomorrow_plan.save()
    from modules.today import services

    assert services.wake_snoozed(tomorrow_plan) == 1
    woken = Task.objects.get(pk=task["id"])
    assert woken.state == "suggested" and woken.snoozed_until is None and woken.prev_state == "snoozed"
    tomorrow_plan.refresh_from_db()
    assert stored_counts(tomorrow_plan.id) == reference_counts(tomorrow_plan.id) and tomorrow_plan.open_count == 1


def test_snoozing_an_own_task_respects_the_quota_of_the_target_day(api, enrolled):
    tomorrow = local_today() + timedelta(days=1)
    for n in range(20):
        add(api, date=tomorrow.isoformat(), title=f"T{n}")
    task = add(api).json_body["task"]
    res = api.post(f"/today/tasks/{task['id']}/snooze/", {"client_id": cid(), "until": "tomorrow"})
    assert res.status_code == 429
    assert Task.objects.get(pk=task["id"]).state == "suggested"  # nothing half done


def test_an_own_task_cannot_be_swapped(api, enrolled):
    task = add(api).json_body["task"]
    res = api.post(f"/today/tasks/{task['id']}/swap/", {"client_id": cid()})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "invalid_transition"
