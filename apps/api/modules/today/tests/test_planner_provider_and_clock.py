"""W8: the planner provider in Today, the cron sweep, retention, the account eraser and the analytics events."""

from datetime import timedelta

import pytest

from core import events
from modules.coverage.models import Enrollment
from modules.today import analytics, erasure, lifecycle, planner_services, registry
from modules.today.models import Milestone, ReplanEvent, StudyPlan, Task

from .conftest import USER
from .helpers import local_today, register_practice

pytestmark = pytest.mark.django_db


@pytest.fixture
def plan(api, enrolled):
    return api.post("/today/planner/").json_body


def behind(subject_key="taxation", days=0, status="pending"):
    """The reading milestone of a paper, dated `days` days ago."""
    Milestone.objects.filter(subject_key=subject_key, kind="finish_reading").update(
        target_date=local_today() - timedelta(days=days), status=status
    )


def open_today(api):
    register_practice()
    return api.post("/today/open/").json_body


def planner_tasks(body):
    return [t for t in body["tasks"] if t["kind"] == "planner_read"]


# ---- the provider -----------------------------------------------------------------------------------------------------------


def test_a_student_without_a_plan_gets_no_planner_task(api, enrolled):
    assert planner_tasks(open_today(api)) == []


def test_a_plan_that_is_on_track_adds_no_task(api, plan):
    assert planner_tasks(open_today(api)) == []


def test_a_paper_behind_its_milestone_gets_a_read_task(api, plan):
    behind(days=1)
    tasks = planner_tasks(open_today(api))
    assert len(tasks) == 1
    task = tasks[0]
    assert task["title"].startswith("Read: ") and task["reason_code"] == "milestone_behind"
    assert "was due 1 day ago" in task["reason"] and task["is_must_do"] is False
    assert task["link"]["path"] == "/app/syllabus"


def test_the_task_is_must_do_only_at_three_days_overdue(api, plan):
    behind(days=3)
    task = planner_tasks(open_today(api))[0]
    assert task["is_must_do"] is True


def test_an_at_risk_plan_is_behind_before_its_date(api, plan):
    behind(days=-5, status="at_risk")
    task = planner_tasks(open_today(api))[0]
    assert task["reason"].startswith("Your plan is behind on") and task["is_must_do"] is False


def test_a_paper_not_yet_due_adds_no_task(api, plan):
    behind(days=-5)
    assert planner_tasks(open_today(api)) == []


def test_the_planner_flag_off_hides_the_provider(api, plan, flag):
    behind(days=4)
    flag(True, planner=False)
    assert planner_tasks(open_today(api)) == []


def test_a_done_milestone_is_not_offered(api, plan):
    behind(days=4)
    Milestone.objects.filter(subject_key="taxation", kind="finish_reading").update(
        status="done", done_at=local_today().isoformat() + "T00:00:00Z"
    )
    assert planner_tasks(open_today(api)) == []


def test_the_provider_is_registered_behind_the_flag():
    spec = registry.get_provider("today.planner")
    assert spec.flag == "today_planner" and [k.name for k in spec.kinds] == ["planner_read"]


def test_reading_a_topic_of_the_chapter_completes_the_task(api, plan):
    behind(days=1)
    task = planner_tasks(open_today(api))[0]
    row = Task.objects.get(pk=task["id"])
    from modules.today import completion

    completion.handle(
        "coverage_event_recorded",
        {
            "user_id": str(USER),
            "event_id": "11111111-1111-1111-1111-111111111111",
            "chapter_id": str(row.chapter_id),
            "type": "topic_done",
            "occurred_at": row.created_at.isoformat(),
        },
    )
    row.refresh_from_db()
    assert row.state == "done"


# ---- the cron sweep ---------------------------------------------------------------------------------------------------------


def age(days, hours=13):
    """The plan was made `days` days ago and last looked at `hours` hours ago."""
    from django.utils import timezone

    StudyPlan.objects.update(
        created_at=timezone.now() - timedelta(days=days), health_checked_at=timezone.now() - timedelta(hours=hours)
    )


def test_two_missed_days_re_plan_automatically(api, plan):
    age(5)
    counts = lifecycle.replan_sweep()
    assert counts["checked"] == 1 and counts["replanned"] == 1 and counts["failed"] == 0
    assert ReplanEvent.objects.count() == 0 or ReplanEvent.objects.get().trigger in ("missed_days", "weekly")
    assert StudyPlan.objects.get().last_replanned_at is not None


def test_a_sweep_with_no_trigger_only_refreshes_the_health(api, plan):
    age(0)
    StudyPlan.objects.update(last_replanned_at=lifecycle.timezone.now())  # re-planned just now: the gap holds
    counts = lifecycle.replan_sweep()
    assert counts == {"checked": 1, "replanned": 0, "refreshed": 1, "archived": 0, "flag_off": 0, "failed": 0}
    assert ReplanEvent.objects.count() == 0


def test_a_plan_looked_at_recently_is_left_alone(api, plan):
    age(5, hours=1)
    assert lifecycle.replan_sweep()["checked"] == 0


def test_the_sweep_does_nothing_for_a_student_with_the_flag_off(api, plan, flag):
    age(5)
    flag(True, planner=False)
    counts = lifecycle.replan_sweep()
    assert counts["flag_off"] == 1 and counts["replanned"] == 0
    assert StudyPlan.objects.get().last_replanned_at is None


def test_a_plan_whose_exam_has_passed_is_archived(api, plan):
    age(5)
    Enrollment.objects.filter(user_id=USER).update(exam_date=local_today() - timedelta(days=1))
    StudyPlan.objects.update(
        exam_date=local_today() - timedelta(days=1), reading_deadline=local_today() - timedelta(days=20)
    )
    assert lifecycle.replan_sweep()["archived"] == 1
    assert StudyPlan.objects.get().status == "archived"


def test_an_automatic_replan_with_no_change_records_nothing(api, plan):
    age(5)
    planner_services.auto_replan(USER)
    first = ReplanEvent.objects.count()
    age(5)
    StudyPlan.objects.update(last_replanned_at=None)
    planner_services.auto_replan(USER)
    assert ReplanEvent.objects.count() == first  # same inputs, same dates: nothing new to tell the student


def test_the_tick_runs_the_planner_sweep(api, plan):
    age(5)
    assert lifecycle.tick()["planner"]["checked"] == 1


def test_old_replan_events_are_pruned_after_24_months(api, plan):
    from django.utils import timezone

    api.post("/today/planner/replan/")
    old = ReplanEvent.objects.get()
    ReplanEvent.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=800))
    api.post("/today/planner/replan/")
    assert lifecycle.prune()["replan_events"] == 1 and ReplanEvent.objects.count() == 1


# ---- the account eraser and exporter ----------------------------------------------------------------------------------------


def test_the_exporter_includes_the_plan_and_the_eraser_removes_it(api, plan):
    api.post("/today/planner/replan/")
    exported = erasure.export_for_user(USER)
    study = exported["study_plans"][0]
    assert study["health"] == "on_track" and study["milestones"] and study["replans"][0]["trigger"] == "manual"
    counts = erasure.delete_all_for_user(USER)
    assert counts["study_plans"] == 1 and counts["milestones"] >= 7 and counts["replan_events"] == 1
    assert not StudyPlan.objects.exists() and not Milestone.objects.exists() and not ReplanEvent.objects.exists()
    assert erasure.delete_all_for_user(USER)["study_plans"] == 0  # idempotent


# ---- analytics --------------------------------------------------------------------------------------------------------------


def test_planner_events_reach_analytics_with_only_schema_properties():
    seen = []
    analytics.set_sink(lambda name, user, props: seen.append((name, props)))
    try:
        events.emit(
            "today_plan_replanned",
            user_id=str(USER),
            trigger="manual",
            health_before="on_track",
            health_after="at_risk",
            moved_count=2,
            option_count=3,
            applied=False,
            title="never sent",
        )
    finally:
        analytics.set_sink(None)
    assert seen == [
        (
            "today_plan_replanned",
            {
                "trigger": "manual",
                "health_before": "on_track",
                "health_after": "at_risk",
                "moved_count": 2,
                "option_count": 3,
                "applied": False,
            },
        )
    ]
