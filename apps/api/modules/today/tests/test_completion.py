"""Events complete tasks: idempotent, reorder-safe, grace after midnight, reconcile on open (PRD 5.3, 5.7, FR-F13-20 to 24)."""

import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from core import events
from modules.coverage import services as coverage_services
from modules.coverage.models import ChapterProgress, CoverageEvent
from modules.today import completion, registry
from modules.today.models import DayPlan, Task, TaskEvidence
from modules.today.registry import CompletionRule, Match

from .conftest import OTHER, USER
from .helpers import cid, local_today, register_fake
from .test_task_actions import reference_counts, stored_counts

pytestmark = pytest.mark.django_db

IST = ZoneInfo("Asia/Kolkata")
EVENT = "fake_event"


def rule(event: registry.Event, task: registry.TaskView):
    """A fake owner's rule: the event names the unit of work (`work`) and how many it answered (`n`, optional)."""
    if event.payload.get("work") != task.dedupe_key:
        return None
    return Match(evidence_key=event.key, done=bool(event.payload.get("exact")), delta=int(event.payload.get("n", 0)))


def provider():
    return register_fake("fake.mcq", [], completion=[CompletionRule(EVENT, rule)])


def make_plan(day, **over):
    return DayPlan.objects.create(user_id=USER, local_date=day, tz="Asia/Kolkata", generation_no=1, **over)


def make_task(plan, key="w1", state="suggested", target=None, **over):
    fields = dict(
        user_id=USER, plan=plan, local_date=plan.local_date, origin="provider", provider="fake.mcq", kind="fake_mcq",
        slot="mcq", dedupe_key=key, title=key, est_minutes=5, state=state, target_value=target,
    )  # fmt: skip
    fields.update(over)
    return Task.objects.create(**fields)


def fire(key, *, work, n=0, exact=False, when=None, user=USER):
    events.emit(
        EVENT,
        user_id=str(user),
        event_id=key,
        occurred_at=(when or timezone.now()).isoformat(),
        work=work,
        n=n,
        exact=exact,
    )


def settle(plan):
    from modules.today import services

    services.settle(plan)


@pytest.fixture
def today_plan(api, enrolled):
    provider()
    plan = make_plan(local_today())
    return plan


# ---- wiring -----------------------------------------------------------------------------------------------------------------


def test_registering_a_provider_subscribes_to_the_events_its_rules_name(today_plan):
    assert EVENT in registry.completion_event_names()
    assert "coverage_event_recorded" in registry.completion_event_names()
    task = make_task(today_plan)
    fire("e1", work="w1", exact=True)
    assert Task.objects.get(pk=task.pk).state == "done"


def test_installing_twice_does_not_subscribe_twice(today_plan):
    completion.install()
    completion.install()
    task = make_task(today_plan)
    fire("e1", work="w1", exact=True)
    assert TaskEvidence.objects.filter(task=task).count() == 1


def test_an_event_that_is_not_about_the_task_changes_nothing(today_plan):
    task = make_task(today_plan)
    fire("e1", work="somebody-else", exact=True)
    assert Task.objects.get(pk=task.pk).state == "suggested" and not TaskEvidence.objects.exists()


def test_a_broken_event_payload_is_ignored(today_plan):
    make_task(today_plan)
    events.emit(EVENT, event_id="e1")  # no user
    events.emit(EVENT, user_id="not-a-uuid", event_id="e1")
    assert not TaskEvidence.objects.exists()


def test_a_rule_that_raises_never_breaks_the_other_tasks(today_plan, monkeypatch):
    good = make_task(today_plan, "good")
    bad = make_task(today_plan, "bad")

    def flaky(event, task):
        if task.dedupe_key == "bad":
            raise RuntimeError("boom")
        return rule(event, task)

    register_fake("fake.mcq", [], completion=[CompletionRule(EVENT, flaky)])
    fire("e1", work="good", exact=True)
    fire("e2", work="bad", exact=True)
    assert Task.objects.get(pk=good.pk).state == "done" and Task.objects.get(pk=bad.pk).state == "suggested"


def test_other_students_tasks_are_never_touched(today_plan):
    theirs = DayPlan.objects.create(user_id=OTHER, local_date=local_today(), tz="Asia/Kolkata", generation_no=1)
    task = make_task(theirs, user_id=OTHER)
    fire("e1", work="w1", exact=True)
    assert Task.objects.get(pk=task.pk).state == "suggested"


# ---- idempotent and reorder-safe --------------------------------------------------------------------------------------------


def test_an_exact_match_completes_the_task_via_event_and_recounts(today_plan):
    task = make_task(today_plan)
    settle(today_plan)
    fire("e1", work="w1", exact=True)
    row = Task.objects.get(pk=task.pk)
    assert (
        row.state == "done"
        and row.completed_via == "event"
        and row.completed_at is not None
        and row.prev_state == "suggested"
    )
    today_plan.refresh_from_db()
    assert (today_plan.done_count, today_plan.open_count) == (1, 0)
    assert stored_counts(today_plan.id) == reference_counts(today_plan.id)


def test_a_replayed_event_changes_nothing(today_plan):
    task = make_task(today_plan)
    fire("e1", work="w1", exact=True)
    snapshot = Task.objects.values().get(pk=task.pk)
    plan_snapshot = DayPlan.objects.values().get(pk=today_plan.pk)
    for _ in range(3):
        fire("e1", work="w1", exact=True)
    assert Task.objects.values().get(pk=task.pk) == snapshot
    assert DayPlan.objects.values().get(pk=today_plan.pk) == plan_snapshot  # not even the version moved
    assert TaskEvidence.objects.filter(task=task).count() == 1


def test_progress_accumulates_to_the_target_and_completes(today_plan):
    task = make_task(today_plan, target=10)
    fire("e1", work="w1", n=4)
    row = Task.objects.get(pk=task.pk)
    assert (row.state, row.progress_value) == ("suggested", 4)
    fire("e2", work="w1", n=4)
    assert Task.objects.get(pk=task.pk).progress_value == 8
    fire("e3", work="w1", n=5)
    row = Task.objects.get(pk=task.pk)
    assert (row.state, row.progress_value, row.completed_via) == ("done", 10, "event")  # capped at the target


@pytest.mark.parametrize("order", [(0, 1, 2), (2, 1, 0), (1, 2, 0), (1, 0, 2)])
def test_out_of_order_and_duplicated_events_give_the_same_result(today_plan, order):
    task = make_task(today_plan, target=9)
    batch = [("a", 3), ("b", 3), ("c", 3)]
    for i in order:
        key, n = batch[i]
        fire(key, work="w1", n=n)
        fire(key, work="w1", n=n)  # delivered twice
    row = Task.objects.get(pk=task.pk)
    assert (row.state, row.progress_value) == ("done", 9)
    assert TaskEvidence.objects.filter(task=task).count() == 3
    today_plan.refresh_from_db()
    assert stored_counts(today_plan.id) == reference_counts(today_plan.id)


def test_an_event_after_done_adds_evidence_but_does_not_change_the_state(today_plan):
    task = make_task(today_plan, target=2)
    fire("e1", work="w1", n=2)
    done_at = Task.objects.get(pk=task.pk).completed_at
    fire("e2", work="w1", n=2)
    row = Task.objects.get(pk=task.pk)
    assert row.state == "done" and row.completed_at == done_at and row.progress_value == 2


def test_done_beats_a_stale_skip_when_activity_arrives(today_plan):
    task = make_task(today_plan, state="skipped", skip_reason="no_time")
    settle(today_plan)
    fire("e1", work="w1", exact=True)
    row = Task.objects.get(pk=task.pk)
    assert row.state == "done" and row.skip_reason is None
    today_plan.refresh_from_db()
    assert stored_counts(today_plan.id) == reference_counts(today_plan.id)


def test_a_snoozed_task_is_completed_by_the_work_too(today_plan):
    task = make_task(today_plan, state="snoozed", snoozed_until=local_today() + timedelta(days=2))
    fire("e1", work="w1", exact=True)
    assert Task.objects.get(pk=task.pk).state == "done"


def test_a_deleted_own_task_is_not_found_by_events(today_plan):
    task = make_task(today_plan, deleted_at=timezone.now())
    fire("e1", work="w1", exact=True)
    assert Task.objects.get(pk=task.pk).state == "suggested"


def test_completion_is_announced_once_even_when_the_event_is_replayed(today_plan, django_capture_on_commit_callbacks):
    seen = []
    events.subscribe("today_task_completed", lambda **p: seen.append(p))
    make_task(today_plan)
    with django_capture_on_commit_callbacks(execute=True):
        fire("e1", work="w1", exact=True)
        fire("e1", work="w1", exact=True)
    assert len(seen) == 1
    assert seen[0]["via"] == "event" and seen[0]["first_of_day"] is True and seen[0]["provider"] == "fake.mcq"


def test_the_finished_day_is_announced_when_the_last_open_task_resolves(today_plan, django_capture_on_commit_callbacks):
    seen = []
    events.subscribe("today_day_completed", lambda **p: seen.append(p))
    make_task(today_plan, "a")
    make_task(today_plan, "b")
    settle(today_plan)
    with django_capture_on_commit_callbacks(execute=True):
        fire("e1", work="a", exact=True)
    assert seen == []  # one task is still open
    with django_capture_on_commit_callbacks(execute=True):
        fire("e2", work="b", exact=True)
    assert len(seen) == 1 and seen[0]["done"] == 2 and seen[0]["completed"] is True


# ---- grace after midnight ---------------------------------------------------------------------------------------------------


def local_at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), tzinfo=IST).astimezone(UTC)


def test_an_event_shortly_after_midnight_completes_yesterdays_open_task(api, enrolled):
    provider()
    yesterday = local_today() - timedelta(days=1)
    task = make_task(make_plan(yesterday), "late")
    fire("e1", work="late", exact=True, when=local_at(local_today(), 1, 30))
    assert Task.objects.get(pk=task.pk).state == "done"


def test_the_grace_covers_a_task_the_day_sweep_already_expired(api, enrolled):
    provider()
    yesterday = local_today() - timedelta(days=1)
    task = make_task(make_plan(yesterday), "late", state="expired", end_reason="day_ended")
    fire("e1", work="late", exact=True, when=local_at(local_today(), 2, 59))
    row = Task.objects.get(pk=task.pk)
    assert row.state == "done" and row.completed_via == "event" and row.prev_state == "suggested"


def test_after_the_grace_yesterdays_task_stays_as_it_was(api, enrolled):
    provider()
    yesterday = local_today() - timedelta(days=1)
    open_one = make_task(make_plan(yesterday), "open-late")
    expired = make_task(
        DayPlan.objects.get(user_id=USER, local_date=yesterday), "gone", state="expired", end_reason="day_ended"
    )
    fire("e1", work="open-late", exact=True, when=local_at(local_today(), 3, 0))
    fire("e2", work="gone", exact=True, when=local_at(local_today(), 4, 0))
    assert Task.objects.get(pk=open_one.pk).state == "suggested" and Task.objects.get(pk=expired.pk).state == "expired"


def test_a_regenerated_task_is_never_revived_by_the_grace(api, enrolled):
    provider()
    yesterday = local_today() - timedelta(days=1)
    task = make_task(make_plan(yesterday), "x", state="expired", end_reason="regenerated")
    fire("e1", work="x", exact=True, when=local_at(local_today(), 1, 0))
    assert Task.objects.get(pk=task.pk).state == "expired"


def test_an_old_event_replayed_today_does_not_complete_todays_task(today_plan):
    task = make_task(today_plan)
    fire("e1", work="w1", exact=True, when=timezone.now() - timedelta(days=5))
    assert Task.objects.get(pk=task.pk).state == "suggested"


def test_an_event_from_late_yesterday_delivered_late_completes_yesterdays_open_task(api, enrolled):
    provider()
    yesterday = local_today() - timedelta(days=1)
    task = make_task(make_plan(yesterday), "w1")
    fire("e1", work="w1", exact=True, when=local_at(yesterday, 22, 10))
    assert Task.objects.get(pk=task.pk).state == "done"


# ---- coverage: the real provider --------------------------------------------------------------------------------------------


@pytest.fixture
def revision_plan(api, enrolled, django_capture_on_commit_callbacks):
    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=1), revision_count=1
    )
    body = api.post("/today/open/").json_body
    task = next(t for t in body["tasks"] if t["kind"] == "revise_chapter")
    return body, task, Task.objects.get(pk=task["id"])


def test_logging_a_revision_in_coverage_completes_the_revision_task(revision_plan, django_capture_on_commit_callbacks):
    _body, _task, row = revision_plan
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.record_event(USER, row.chapter_id, CoverageEvent.Type.REVISION_DONE, client_id=uuid.uuid4())
    row.refresh_from_db()
    assert row.state == "done" and row.completed_via == "event"
    ev = TaskEvidence.objects.get(task=row)
    assert ev.event_name == "coverage_event_recorded" and ev.completes


def test_a_revision_of_another_chapter_does_not_complete_it(revision_plan, django_capture_on_commit_callbacks):
    _b, _t, row = revision_plan
    other = ChapterProgress.objects.filter(user_id=USER).exclude(chapter_id=row.chapter_id).first()
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.record_event(USER, other.chapter_id, CoverageEvent.Type.REVISION_DONE, client_id=uuid.uuid4())
    assert Task.objects.get(pk=row.pk).state == "suggested"


def test_ticking_the_topic_completes_the_next_topic_task(api, enrolled, django_capture_on_commit_callbacks):
    from modules.syllabus.models import Topic

    first = Topic.objects.get(key="eligibility", chapter__key="gst-itc")
    second = Topic.objects.get(key="blocked-credit", chapter__key="gst-itc")
    coverage_services.tick_topic(USER, first.id, done=True)  # the chapter is now in progress
    api.put("/today/settings/", {"minutes_per_day": 240})
    body = api.post("/today/open/").json_body
    task = next(t for t in body["tasks"] if t["kind"] == "next_topic" and t["chapter_id"] == str(first.chapter_id))
    row = Task.objects.get(pk=task["id"])
    assert row.dedupe_key == f"topic:{second.id}"
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.tick_topic(USER, second.id, done=True)
    assert Task.objects.get(pk=row.pk).state == "done"


def test_starting_a_chapter_completes_the_next_chapter_task(api, enrolled, django_capture_on_commit_callbacks):
    body = api.post("/today/open/").json_body
    task = next(t for t in body["tasks"] if t["kind"] == "next_chapter")
    row = Task.objects.get(pk=task["id"])
    from modules.syllabus.models import Topic

    topic = Topic.objects.filter(chapter_id=row.chapter_id).order_by("sort_order").first()
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.tick_topic(USER, topic.id, done=True)
    assert Task.objects.get(pk=row.pk).state == "done"


# ---- the coverage emit ------------------------------------------------------------------------------------------------------


def test_coverage_announces_each_new_event_once_and_not_a_replay(enrolled, django_capture_on_commit_callbacks):
    seen = []
    events.subscribe("coverage_event_recorded", lambda **p: seen.append(p))
    chapter = ChapterProgress.objects.filter(user_id=USER).first().chapter_id
    client = uuid.uuid4()
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.record_event(USER, chapter, CoverageEvent.Type.REVISION_DONE, client_id=client)
    with django_capture_on_commit_callbacks(execute=True):
        coverage_services.record_event(USER, chapter, CoverageEvent.Type.REVISION_DONE, client_id=client)  # a retry
    mine = [p for p in seen if p["event_id"] and p["chapter_id"] == str(chapter)]
    assert len(mine) == 1
    payload = mine[0]
    assert set(payload) == {
        "user_id",
        "event_id",
        "chapter_id",
        "subject_id",
        "topic_id",
        "type",
        "source",
        "source_ref",
        "occurred_at",
    }
    assert payload["type"] == "revision_done" and payload["user_id"] == USER and payload["topic_id"] is None
    assert CoverageEvent.objects.filter(pk=payload["event_id"]).exists()


def test_a_failing_subscriber_never_breaks_the_coverage_write(enrolled, django_capture_on_commit_callbacks):
    events.subscribe("coverage_event_recorded", lambda **p: 1 / 0)
    chapter = ChapterProgress.objects.filter(user_id=USER).first().chapter_id
    with django_capture_on_commit_callbacks(execute=True):
        event = coverage_services.record_event(USER, chapter, CoverageEvent.Type.REVISION_DONE, client_id=uuid.uuid4())
    assert CoverageEvent.objects.filter(pk=event.pk).exists()


def test_the_manual_actions_own_event_does_not_complete_a_task_twice(api, enrolled, django_capture_on_commit_callbacks):
    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=1), revision_count=1
    )
    body = api.post("/today/open/").json_body
    task = next(t for t in body["tasks"] if t["kind"] == "revise_chapter")
    with django_capture_on_commit_callbacks(execute=True):
        api.post(f"/today/tasks/{task['id']}/complete/", {"client_id": cid(), "run_manual_action": True})
    row = Task.objects.get(pk=task["id"])
    assert row.state == "done" and row.completed_via == "manual"  # the student's tick stands; the echo changed nothing
    plan = DayPlan.objects.get(pk=row.plan_id)
    assert stored_counts(plan.id) == reference_counts(plan.id) and plan.done_count == 1


# ---- reconcile --------------------------------------------------------------------------------------------------------------


def test_open_completes_tasks_whose_work_was_done_while_no_event_arrived(api, enrolled):
    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=1), revision_count=1
    )
    body = api.post("/today/open/").json_body
    task = next(t for t in body["tasks"] if t["kind"] == "revise_chapter")
    row = Task.objects.get(pk=task["id"])
    # the student revised on another device and the event never reached us
    ChapterProgress.objects.filter(user_id=USER, chapter_id=row.chapter_id).update(revision_count=2)
    from django.core.cache import cache

    cache.clear()  # the 30 second guard
    again = api.post("/today/open/").json_body
    done = next(t for t in again["tasks"] if t["id"] == task["id"])
    assert done["state"] == "done" and again["counts"]["done"] >= 1 and again["created"] is False
    row.refresh_from_db()
    assert row.completed_via == "event"
    assert TaskEvidence.objects.get(task=row).event_name == "reconcile"


def test_reconcile_runs_at_most_every_thirty_seconds(api, enrolled):
    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=1), revision_count=1
    )
    body = api.post("/today/open/").json_body
    task = next(t for t in body["tasks"] if t["kind"] == "revise_chapter")
    row = Task.objects.get(pk=task["id"])
    api.post("/today/open/")  # first reconcile (nothing to do) arms the guard
    ChapterProgress.objects.filter(user_id=USER, chapter_id=row.chapter_id).update(revision_count=2)
    still = api.post("/today/open/").json_body
    assert next(t for t in still["tasks"] if t["id"] == task["id"])["state"] == "suggested"


def test_reconcile_twice_is_harmless(api, enrolled):
    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=1), revision_count=1
    )
    body = api.post("/today/open/").json_body
    row = Task.objects.get(pk=next(t for t in body["tasks"] if t["kind"] == "revise_chapter")["id"])
    ChapterProgress.objects.filter(user_id=USER, chapter_id=row.chapter_id).update(revision_count=2)
    plan = DayPlan.objects.get(pk=row.plan_id)
    assert completion.reconcile_plan(plan, force=True) == 1
    snapshot = Task.objects.values().get(pk=row.pk)
    assert completion.reconcile_plan(plan, force=True) == 0
    assert Task.objects.values().get(pk=row.pk) == snapshot


def test_a_provider_that_cannot_answer_leaves_its_tasks_alone(today_plan):
    task = make_task(today_plan)

    def broken(user_id, tasks, day):
        raise RuntimeError("down")

    register_fake("fake.mcq", [], reconcile=broken)
    assert completion.reconcile_plan(today_plan, force=True) == 0
    assert Task.objects.get(pk=task.pk).state == "suggested"


def test_get_plan_never_reconciles_or_writes(api, enrolled):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=1), revision_count=1
    )
    body = api.post("/today/open/").json_body
    row = Task.objects.get(pk=next(t for t in body["tasks"] if t["kind"] == "revise_chapter")["id"])
    ChapterProgress.objects.filter(user_id=USER, chapter_id=row.chapter_id).update(revision_count=2)
    with CaptureQueriesContext(connection) as queries:
        res = api.get("/today/plan/")
    assert next(t for t in res.json_body["tasks"] if t["id"] == str(row.id))["state"] == "suggested"
    assert not [q for q in queries if q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))]


def test_reconcile_ignores_the_students_own_tasks(api, enrolled):
    body = api.post("/today/tasks/", {"client_id": cid(), "title": "Mine", "est_minutes": 5}).json_body
    api.post("/today/open/")
    again = api.post("/today/open/").json_body
    own = next(t for t in again["tasks"] if t["id"] == body["task"]["id"])
    assert own["state"] == "suggested"
