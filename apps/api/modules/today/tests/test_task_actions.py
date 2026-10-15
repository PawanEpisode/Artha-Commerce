"""start, complete, skip, snooze, swap, undo: the state machine over HTTP, replays, conflicts, recount (PRD 5.2, ERD 3.5)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from modules.today.models import DayPlan, Task
from modules.today.registry import KindSpec

from .conftest import OTHER, USER
from .helpers import candidate, cid, local_today, register_fake, register_practice

pytestmark = pytest.mark.django_db


@pytest.fixture
def plan(api, enrolled):
    register_practice()
    return api.post("/today/open/").json_body


def url(task_id, action):
    return f"/today/tasks/{task_id}/{action}/"


def first_open(plan_body):
    return next(t for t in plan_body["tasks"] if t["origin"] == "provider" and t["state"] == "suggested")


def reference_counts(plan_id):
    """The counters recomputed from the rows with plain Python: the property the stored columns must keep."""
    rows = Task.objects.filter(plan_id=plan_id, deleted_at__isnull=True).exclude(state="expired")
    counts = {"planned": 0, "done": 0, "open": 0, "skipped": 0, "snoozed": 0}
    for t in rows:
        if t.state == "snoozed":
            counts["snoozed"] += 1
        if not t.counts_toward_day:
            continue
        if t.state in ("suggested", "accepted", "done", "skipped"):
            counts["planned"] += 1
        if t.state == "done":
            counts["done"] += 1
        if t.state == "skipped":
            counts["skipped"] += 1
        if t.state in ("suggested", "accepted"):
            counts["open"] += 1
    return counts


def stored_counts(plan_id):
    p = DayPlan.objects.get(pk=plan_id)
    return {
        "planned": p.planned_count,
        "done": p.done_count,
        "open": p.open_count,
        "skipped": p.skipped_count,
        "snoozed": p.snoozed_count,
    }


# ---- start ------------------------------------------------------------------------------------------------------------------


def test_start_marks_accepted_and_returns_the_link(api, plan):
    task = first_open(plan)
    res = api.post(url(task["id"], "start"), {"client_id": cid()})
    assert res.status_code == 200
    body = res.json_body
    assert body["task"]["state"] == "accepted" and body["link"]["path"].startswith("/app/")
    assert body["task"]["version"] == task["version"] + 1 and body["counts"]["open"] == plan["counts"]["open"]


def test_starting_twice_is_a_no_op(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "start"), {"client_id": cid()})
    again = api.post(url(task["id"], "start"), {"client_id": cid()}).json_body
    assert again["task"]["state"] == "accepted" and again["task"]["version"] == task["version"] + 1


# ---- complete ---------------------------------------------------------------------------------------------------------------


def test_complete_updates_the_counters(api, plan):
    task = first_open(plan)
    body = api.post(url(task["id"], "complete"), {"client_id": cid()}).json_body
    assert body["task"]["state"] == "done"
    assert body["counts"]["done"] == 1 and body["counts"]["open"] == plan["counts"]["open"] - 1
    row = Task.objects.get(pk=task["id"])
    assert row.completed_via == "manual" and row.completed_at is not None and row.prev_state == "suggested"


def test_complete_is_idempotent_for_the_same_and_for_another_client_id(api, plan):
    task = first_open(plan)
    c1 = cid()
    first = api.post(url(task["id"], "complete"), {"client_id": c1}).json_body
    same = api.post(url(task["id"], "complete"), {"client_id": c1}).json_body
    other = api.post(url(task["id"], "complete"), {"client_id": cid()}).json_body
    assert first["task"] == same["task"] == other["task"]
    assert other["counts"]["done"] == 1


def test_complete_runs_the_manual_action_once(api, enrolled):
    from modules.coverage.models import ChapterProgress, CoverageEvent

    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=1), revision_count=1
    )
    body = api.post("/today/open/").json_body
    task = next(t for t in body["tasks"] if t["kind"] == "revise_chapter")
    assert task["manual_action"]["default"] is True
    before = CoverageEvent.objects.filter(user_id=USER, type="revision_done").count()
    api.post(url(task["id"], "complete"), {"client_id": cid(), "run_manual_action": True})
    api.post(url(task["id"], "undo"), {"client_id": cid(), "from_state": "done"})
    api.post(url(task["id"], "complete"), {"client_id": cid(), "run_manual_action": True})
    assert (
        CoverageEvent.objects.filter(user_id=USER, type="revision_done").count() == before + 1
    )  # logged once, not per tick


def test_a_failing_manual_action_does_not_block_the_tick(api, enrolled, monkeypatch):
    from modules.coverage import today_providers
    from modules.coverage.models import ChapterProgress

    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=1), revision_count=1
    )
    task = next(t for t in api.post("/today/open/").json_body["tasks"] if t["kind"] == "revise_chapter")
    monkeypatch.setattr(today_providers.services, "record_event", lambda *a, **k: 1 / 0)
    res = api.post(url(task["id"], "complete"), {"client_id": cid(), "run_manual_action": True})
    assert res.status_code == 200 and res.json_body["task"]["state"] == "done"


# ---- skip -------------------------------------------------------------------------------------------------------------------


def test_skip_records_the_reason_and_the_counts(api, plan):
    task = first_open(plan)
    body = api.post(url(task["id"], "skip"), {"client_id": cid(), "reason": "no_time"}).json_body
    assert body["task"]["state"] == "skipped" and body["suppressed_days"] is None
    assert Task.objects.get(pk=task["id"]).skip_reason == "no_time"
    assert body["counts"]["skipped"] == 1


def test_swapped_is_not_a_reason_a_student_can_send(api, plan):
    res = api.post(url(first_open(plan)["id"], "skip"), {"client_id": cid(), "reason": "swapped"})
    assert res.status_code == 400


def test_the_third_skip_in_two_weeks_reports_suppression(api, plan):
    today = local_today()
    for n in (1, 2):  # two skips of the same work on earlier days
        past = DayPlan.objects.create(
            user_id=USER, local_date=today - timedelta(days=n), tz="Asia/Kolkata", generation_no=1
        )
        Task.objects.create(
            user_id=USER, plan=past, local_date=past.local_date, origin="provider", provider="fake.practice", kind="fake_mcq",
            slot="mcq", dedupe_key="same-key", title="t", est_minutes=5, state="skipped", skip_reason="no_time",
        )  # fmt: skip
    task = first_open(plan)
    Task.objects.filter(pk=task["id"]).update(dedupe_key="same-key")
    body = api.post(url(task["id"], "skip"), {"client_id": cid()}).json_body
    assert body["suppressed_days"] == 14


def test_a_second_skip_is_not_yet_suppression(api, plan):
    past = DayPlan.objects.create(
        user_id=USER, local_date=local_today() - timedelta(days=1), tz="Asia/Kolkata", generation_no=1
    )
    Task.objects.create(
        user_id=USER, plan=past, local_date=past.local_date, origin="provider", provider="fake.practice", kind="fake_mcq",
        slot="mcq", dedupe_key="same-key", title="t", est_minutes=5, state="skipped",
    )  # fmt: skip
    task = first_open(plan)
    Task.objects.filter(pk=task["id"]).update(dedupe_key="same-key")
    assert api.post(url(task["id"], "skip"), {"client_id": cid()}).json_body["suppressed_days"] is None


# ---- snooze -----------------------------------------------------------------------------------------------------------------


def test_snooze_a_provider_task_keeps_it_in_the_plan_as_snoozed(api, plan):
    task = first_open(plan)
    body = api.post(url(task["id"], "snooze"), {"client_id": cid(), "until": "tomorrow"}).json_body
    assert body["task"]["state"] == "snoozed" and body["counts"]["snoozed"] == 1
    row = Task.objects.get(pk=task["id"])
    assert row.snoozed_until == local_today() + timedelta(days=1) and row.snooze_count == 1


@pytest.mark.parametrize("preset,days", [("tomorrow", 1), ("in_3_days", 3), ("next_week", 7)])
def test_snooze_presets(api, plan, preset, days):
    task = first_open(plan)
    api.post(url(task["id"], "snooze"), {"client_id": cid(), "until": preset})
    assert Task.objects.get(pk=task["id"]).snoozed_until == local_today() + timedelta(days=days)


def test_snooze_dates_out_of_range_are_refused(api, plan):
    task = first_open(plan)
    for until in (local_today().isoformat(), (local_today() + timedelta(days=31)).isoformat(), "someday"):
        res = api.post(url(task["id"], "snooze"), {"client_id": cid(), "until": until})
        assert res.status_code == 400, until
    assert api.post(url(task["id"], "snooze"), {"client_id": cid(), "until": "tomorrow"}).status_code == 200


def test_a_snoozed_provider_task_is_not_offered_again_until_its_date(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "snooze"), {"client_id": cid(), "until": "in_3_days"})
    from modules.today import generation, selectors

    history = selectors.key_history(USER, local_today(), None)
    assert Task.objects.get(pk=task["id"]).dedupe_key in history.suppressed_keys
    assert generation  # imported for the suppression path the next generation takes


# ---- undo -------------------------------------------------------------------------------------------------------------------


def test_undo_a_tick_within_the_window_restores_the_state_and_counters(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "complete"), {"client_id": cid()})
    body = api.post(url(task["id"], "undo"), {"client_id": cid(), "from_state": "done"}).json_body
    assert body["task"]["state"] == "suggested" and body["counts"]["done"] == 0
    row = Task.objects.get(pk=task["id"])
    assert row.completed_at is None and row.completed_via is None


def test_undo_after_the_window_is_410(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "complete"), {"client_id": cid()})
    Task.objects.filter(pk=task["id"]).update(state_changed_at=timezone.now() - timedelta(seconds=61))
    res = api.post(url(task["id"], "undo"), {"client_id": cid(), "from_state": "done"})
    assert res.status_code == 410 and res.json_body["error"]["code"] == "undo_expired"


def test_undo_with_the_wrong_from_state_is_invalid_transition(api, plan):
    task = first_open(plan)
    res = api.post(url(task["id"], "undo"), {"client_id": cid(), "from_state": "done"})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "invalid_transition"
    assert res.json_body["error"]["details"]["state"] == "suggested"


def test_undo_a_skip_goes_back_to_suggested(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "skip"), {"client_id": cid(), "reason": "other"})
    body = api.post(url(task["id"], "undo"), {"client_id": cid(), "from_state": "skipped"}).json_body
    assert body["task"]["state"] == "suggested" and Task.objects.get(pk=task["id"]).skip_reason is None


def test_a_tick_made_by_activity_cannot_be_undone(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "complete"), {"client_id": cid()})
    Task.objects.filter(pk=task["id"]).update(completed_via="event")
    res = api.post(url(task["id"], "undo"), {"client_id": cid(), "from_state": "done"})
    assert res.status_code == 422 and res.json_body["error"]["details"]["allowed"] == []


# ---- cross device -----------------------------------------------------------------------------------------------------------


def test_a_stale_skip_never_beats_done(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "complete"), {"client_id": cid()})
    res = api.post(
        url(task["id"], "skip"), {"client_id": cid(), "client_ts": (timezone.now() + timedelta(minutes=5)).isoformat()}
    )
    assert res.status_code == 409 and res.json_body["error"]["code"] == "state_conflict"
    assert res.json_body["error"]["details"]["task"]["state"] == "done"
    assert Task.objects.get(pk=task["id"]).state == "done"


def test_a_stale_snooze_and_swap_never_beat_done(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "complete"), {"client_id": cid()})
    assert api.post(url(task["id"], "snooze"), {"client_id": cid(), "until": "tomorrow"}).status_code == 409
    assert api.post(url(task["id"], "swap"), {"client_id": cid()}).status_code == 409


def test_a_completion_beats_a_skip_made_on_another_device(api, plan):
    task = first_open(plan)
    api.post(url(task["id"], "skip"), {"client_id": cid(), "reason": "no_time"})
    body = api.post(url(task["id"], "complete"), {"client_id": cid()}).json_body
    assert body["task"]["state"] == "done"
    row = Task.objects.get(pk=task["id"])
    assert row.skip_reason is None and row.prev_state == "suggested"
    assert stored_counts(row.plan_id) == reference_counts(row.plan_id)


def test_between_open_states_the_later_client_ts_wins(api, plan):
    task = first_open(plan)
    now = timezone.now()
    api.post(url(task["id"], "snooze"), {"client_id": cid(), "until": "tomorrow", "client_ts": now.isoformat()})
    late = api.post(
        url(task["id"], "skip"), {"client_id": cid(), "client_ts": (now - timedelta(minutes=10)).isoformat()}
    )
    assert late.status_code == 409 and late.json_body["error"]["details"]["task"]["state"] == "snoozed"


def test_a_repeated_client_id_writes_nothing(api, plan):
    task = first_open(plan)
    c1 = cid()
    first = api.post(url(task["id"], "skip"), {"client_id": c1, "reason": "no_time"}).json_body
    version = Task.objects.get(pk=task["id"]).version
    again = api.post(url(task["id"], "skip"), {"client_id": c1, "reason": "other"}).json_body
    assert again["task"] == first["task"] and Task.objects.get(pk=task["id"]).version == version
    assert Task.objects.get(pk=task["id"]).skip_reason == "no_time"


# ---- swap -------------------------------------------------------------------------------------------------------------------


def test_swap_replaces_a_suggestion_with_another_of_the_same_group(api, enrolled):
    register_practice()
    plan = api.post("/today/open/").json_body
    task = first_open(plan)
    # give the swap something that is not in the plan yet
    register_fake(
        "fake.extra",
        [candidate("extra-mcq", "extra_mcq", None, 6, (90, 90, 90, 90))],
        kinds=[KindSpec("extra_mcq", "practice", "mcq", "ListChecks", 6)],
    )
    res = api.post(url(task["id"], "swap"), {"client_id": cid()})
    assert res.status_code == 200, res.json_body
    body = res.json_body
    assert body["old"]["state"] == "skipped" and body["new"]["state"] == "suggested"
    assert Task.objects.get(pk=task["id"]).skip_reason == "swapped"
    new = Task.objects.get(pk=body["new"]["id"])
    assert str(new.swapped_from_id) == task["id"] and new.position == Task.objects.get(pk=task["id"]).position


def test_swap_without_an_alternative_is_422(api, enrolled):
    register_fake("fake.mcq", [candidate("only")])
    plan = api.post("/today/open/").json_body
    task = next(t for t in plan["tasks"] if t["kind"] == "fake_mcq")
    res = api.post(url(task["id"], "swap"), {"client_id": cid()})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "no_alternative"
    assert Task.objects.get(pk=task["id"]).state == "suggested"  # nothing changed


def test_a_swap_retry_returns_the_same_pair(api, enrolled):
    register_practice()
    plan = api.post("/today/open/").json_body
    task = first_open(plan)
    register_fake(
        "fake.extra",
        [candidate("extra-mcq", "extra_mcq", None, 6, (90, 90, 90, 90))],
        kinds=[KindSpec("extra_mcq", "practice", "mcq", "ListChecks", 6)],
    )
    c1 = cid()
    first = api.post(url(task["id"], "swap"), {"client_id": c1})
    assert first.status_code == 200, first.json_body
    again = api.post(url(task["id"], "swap"), {"client_id": c1}).json_body
    assert again["new"]["id"] == first.json_body["new"]["id"]
    assert Task.objects.filter(swapped_from_id=task["id"]).count() == 1


def test_swaps_are_limited_to_twenty_a_day(api, plan):
    plan_row = DayPlan.objects.get(user_id=USER, local_date=local_today())
    for n in range(20):
        Task.objects.create(
            user_id=USER, plan=plan_row, local_date=plan_row.local_date, origin="provider", provider="fake.practice",
            kind="fake_mcq", slot="mcq", dedupe_key=f"old{n}", title="t", est_minutes=5, state="skipped",
            skip_reason="swapped", swapped_from_id=plan["tasks"][0]["id"],
        )  # fmt: skip
    res = api.post(url(first_open(plan)["id"], "swap"), {"client_id": cid()})
    assert res.status_code == 429 and res.json_body["error"]["code"] == "quota_exceeded"
    assert res.json_body["error"]["details"]["limit"] == 20


# ---- access -----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("action", ["start", "complete", "skip", "snooze", "swap", "undo"])
def test_another_students_task_is_404(other_api, plan, action):
    body = {"client_id": cid(), "until": "tomorrow", "from_state": "done"}
    res = other_api.post(url(first_open(plan)["id"], action), body)
    assert res.status_code == 404 and res.json_body["error"]["code"] == "task_not_found"


def test_actions_need_a_client_id(api, plan):
    assert api.post(url(first_open(plan)["id"], "complete"), {}).status_code == 400


def test_no_other_students_data_changes(api, other_api, plan):
    first_open_id = first_open(plan)["id"]
    other_api.post(url(first_open_id, "skip"), {"client_id": cid()})
    assert Task.objects.get(pk=first_open_id).state == "suggested"
    assert OTHER  # the second student exists only to attempt the write
