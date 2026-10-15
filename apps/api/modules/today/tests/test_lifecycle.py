"""W6: the cron tick, the day sweep, pre-generation, prune, the digest, the eraser and exporter, and the stuck own task."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from core import events
from modules.today import analytics, lifecycle, selectors, services
from modules.today.models import DayPlan, Task, TaskEvidence, TodaySettings

from .conftest import USER
from .helpers import cid, local_today, register_many, register_practice

pytestmark = pytest.mark.django_db


@pytest.fixture
def plan(api, enrolled):
    register_practice()
    register_many()
    api.put("/today/settings/", {"minutes_per_day": 240})
    return api.post("/today/open/").json_body


def after_grace(day, tz, minutes=0):
    """A moment `minutes` after the 03:00 grace of the day after `day`, in `tz`."""
    return datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=ZoneInfo(tz)) + timedelta(
        hours=3, minutes=minutes
    )


def add_own(api, title, day=None, minutes=10):
    day = day or local_today()
    res = api.post(
        "/today/tasks/", {"client_id": cid(), "title": title, "date": day.isoformat(), "est_minutes": minutes}
    )
    assert res.status_code == 201, res.json_body
    return res.json_body["task"]


# ---- the tick endpoint ---------------------------------------------------------------------------------------------------


def test_tick_refuses_a_missing_wrong_or_unset_secret(client, settings):
    settings.TODAY_TICK_SECRET = "s3cret-value"
    assert client.post("/api/v1/today/internal/tick/").status_code == 403
    assert client.post("/api/v1/today/internal/tick/", HTTP_X_TODAY_TICK_SECRET="nope").status_code == 403
    settings.TODAY_TICK_SECRET = ""
    assert client.post("/api/v1/today/internal/tick/", HTTP_X_TODAY_TICK_SECRET="").status_code == 403


def test_tick_runs_with_the_secret_or_the_bearer_form_whatever_the_flag_says(client, settings, flag):
    flag(False)
    settings.TODAY_TICK_SECRET = "s3cret-value"
    res = client.post("/api/v1/today/internal/tick/", HTTP_X_TODAY_TICK_SECRET="s3cret-value")
    assert res.status_code == 200
    assert set(res.json()) == {"close", "pregenerate", "planner", "prune"}
    res = client.get("/api/v1/today/internal/tick/", HTTP_AUTHORIZATION="Bearer s3cret-value")
    assert res.status_code == 200


# ---- the day sweep -------------------------------------------------------------------------------------------------------


def test_a_day_closes_only_after_the_grace_and_only_once(api, plan):
    day, tz = local_today(), plan["tz"]
    DayPlan_ = DayPlan.objects.get(user_id=USER, local_date=day)
    assert lifecycle.close_sweep(after_grace(day, tz, -1))["closed"] == 0
    first = lifecycle.close_sweep(after_grace(day, tz, 1))
    assert first["closed"] == 1 and first["expired"] >= 1
    DayPlan_.refresh_from_db()
    assert DayPlan_.status == "closed" and DayPlan_.closed_at is not None
    assert lifecycle.close_sweep(after_grace(day, tz, 2)) == {"closed": 0, "expired": 0, "carried": 0}


def test_open_provider_tasks_expire_and_the_record_counts_them_as_left(api, plan):
    day, tz = local_today(), plan["tz"]
    done = plan["tasks"][0]["id"]
    assert api.post(f"/today/tasks/{done}/complete/", {"client_id": cid()}).status_code == 200
    planned = plan["counts"]["planned"]
    lifecycle.close_sweep(after_grace(day, tz, 1))
    row = DayPlan.objects.get(user_id=USER, local_date=day)
    assert (row.planned_count, row.done_count, row.open_count) == (planned, 1, 0)
    assert row.skipped_count == planned - 1
    expired = Task.objects.filter(plan=row, state="expired")
    assert expired.count() == planned - 1
    assert all(t.end_reason == "day_ended" for t in expired)
    recap = api.get(f"/today/plan/?date={day.isoformat()}").json_body
    assert {t["state"] for t in recap["tasks"]} <= {"done", "skipped"}  # nothing reads as open or expired


def test_day_closed_is_announced_once_with_the_outcome(api, plan, django_capture_on_commit_callbacks):
    day, tz = local_today(), plan["tz"]
    got = []
    listener = lambda **p: got.append(p)  # noqa: E731
    events.subscribe(lifecycle.DAY_CLOSED, listener)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            lifecycle.close_sweep(after_grace(day, tz, 1))
        with django_capture_on_commit_callbacks(execute=True):
            lifecycle.close_sweep(after_grace(day, tz, 5))
    finally:
        events._subscribers[lifecycle.DAY_CLOSED].remove(listener)
    assert len(got) == 1
    assert got[0]["planned"] == plan["counts"]["planned"] and got[0]["done"] == 0
    assert got[0]["expired"] == plan["counts"]["planned"] and got[0]["completed"] is False


def test_an_own_task_is_carried_three_times_then_flagged_stuck_then_expires(api, plan):
    day, tz = local_today(), plan["tz"]
    task = add_own(api, "Revise depreciation")
    seen = []
    for n in range(1, 4):
        lifecycle.close_sweep(after_grace(day, tz, 1))
        day = day + timedelta(days=1)
        row = Task.objects.get(pk=task["id"])
        assert row.local_date == day and row.carry_count == n and row.state == "suggested"
        seen.append(row.plan_id)
    assert len(set(seen)) == 3
    # on day 4 the student sees the prompt
    row = Task.objects.get(pk=task["id"])
    opened = services.open_today(USER, now=after_grace(day - timedelta(days=1), tz, 30))
    shown = next(t for t in api.get(f"/today/plan/?date={day.isoformat()}").json_body["tasks"] if t["id"] == task["id"])
    assert opened.plan is not None and shown["stuck"] is True
    # ... and if it is still open when day 4 ends it expires rather than moving on a fourth time
    lifecycle.close_sweep(after_grace(day, tz, 1))
    row.refresh_from_db()
    assert row.state == "expired" and row.carry_count == 3


def test_keep_snooze_and_delete_answer_the_stuck_prompt(api, plan):
    task = add_own(api, "Stuck one")
    Task.objects.filter(pk=task["id"]).update(carry_count=3)
    shown = api.get("/today/plan/").json_body
    stuck = next(t for t in shown["tasks"] if t["id"] == task["id"])
    assert stuck["stuck"] is True
    kept = api.patch(f"/today/tasks/{task['id']}/", {"version": stuck["version"], "keep": True})
    assert kept.status_code == 200 and kept.json_body["task"]["stuck"] is False
    Task.objects.filter(pk=task["id"]).update(carry_count=3)
    snoozed = api.post(f"/today/tasks/{task['id']}/snooze/", {"client_id": cid(), "until": "tomorrow"})
    assert snoozed.status_code == 200
    assert Task.objects.get(pk=task["id"]).carry_count == 0


def test_the_sweep_never_touches_a_provider_task_that_is_done_or_skipped(api, plan):
    day, tz = local_today(), plan["tz"]
    ids = [t["id"] for t in plan["tasks"]]
    api.post(f"/today/tasks/{ids[0]}/complete/", {"client_id": cid()})
    api.post(f"/today/tasks/{ids[1]}/skip/", {"client_id": cid()})
    lifecycle.close_sweep(after_grace(day, tz, 1))
    assert Task.objects.get(pk=ids[0]).state == "done"
    assert Task.objects.get(pk=ids[1]).state == "skipped"


# ---- pre-generation ------------------------------------------------------------------------------------------------------


def test_a_student_who_used_today_yesterday_gets_a_plan_that_is_not_opened(api, plan):
    day, tz = local_today(), plan["tz"]
    nxt = after_grace(day, tz, -170)  # 00:10 of the next day
    out = lifecycle.pregenerate(nxt)
    assert out["pregenerated"] == 1
    tomorrow = DayPlan.objects.get(user_id=USER, local_date=day + timedelta(days=1))
    assert tomorrow.status == "ready" and tomorrow.first_opened_at is None and tomorrow.planned_count > 0
    assert lifecycle.pregenerate(nxt)["pregenerated"] == 0  # a second tick makes nothing
    opened = services.open_today(USER, now=nxt + timedelta(hours=7))
    tomorrow.refresh_from_db()
    assert opened.created is False and tomorrow.first_opened_at is not None


def test_pregeneration_skips_students_who_never_opened_today_and_students_with_the_flag_off(api, plan, flag):
    day, tz = local_today(), plan["tz"]
    nxt = after_grace(day, tz, -170)
    flag(False)
    assert lifecycle.pregenerate(nxt)["pregenerated"] == 0
    flag(True)
    DayPlan.objects.filter(user_id=USER).update(first_opened_at=None)
    assert lifecycle.pregenerate(nxt)["checked"] == 0


def test_a_student_inactive_for_a_week_is_left_alone(api, plan):
    day, tz = local_today(), plan["tz"]
    assert lifecycle.pregenerate(after_grace(day + timedelta(days=9), tz, -170))["checked"] == 0


def test_the_tick_closes_before_it_pregenerates_so_a_carried_task_lands_in_the_new_plan(api, plan):
    day, tz = local_today(), plan["tz"]
    task = add_own(api, "Carry me")
    out = lifecycle.tick(after_grace(day, tz, 5))
    assert out["close"]["carried"] == 1 and out["pregenerate"]["pregenerated"] == 1
    carried = Task.objects.get(pk=task["id"])
    assert carried.local_date == day + timedelta(days=1) and carried.plan.status == "ready"
    assert carried.plan.open_count >= 1


# ---- prune ---------------------------------------------------------------------------------------------------------------


def test_prune_removes_old_evidence_tasks_and_empty_plans_only(api, plan):
    day = local_today()
    task = Task.objects.filter(plan__user_id=USER).first()
    old = TaskEvidence.objects.create(
        task=task, user_id=USER, event_name="x", event_key="old", occurred_at=datetime.now(ZoneInfo("UTC"))
    )
    TaskEvidence.objects.filter(pk=old.pk).update(created_at=datetime.now(ZoneInfo("UTC")) - timedelta(days=91))
    fresh = TaskEvidence.objects.create(
        task=task, user_id=USER, event_name="x", event_key="fresh", occurred_at=datetime.now(ZoneInfo("UTC"))
    )
    out = lifecycle.prune(datetime.now(ZoneInfo("UTC")))
    assert out["evidence"] == 1 and out["tasks"] == 0
    assert TaskEvidence.objects.filter(pk=fresh.pk).exists() and not TaskEvidence.objects.filter(pk=old.pk).exists()
    far = datetime.now(ZoneInfo("UTC")) + timedelta(days=31 * 14)
    out = lifecycle.prune(far)
    assert out["tasks"] > 0
    assert DayPlan.objects.filter(user_id=USER, local_date=day).exists()  # a plan stays 24 months
    out = lifecycle.prune(datetime.now(ZoneInfo("UTC")) + timedelta(days=800))
    assert out["plans"] == 1


# ---- the digest ----------------------------------------------------------------------------------------------------------


def test_the_digest_counts_open_work_and_stops_when_done(api, plan):
    day = local_today()
    digest = selectors.reminder_digest(USER, day)
    assert digest["has_plan"] and digest["is_done"] is False
    assert digest["open_count"] == plan["counts"]["open"] and len(digest["top"]) <= 3
    assert set(digest["top"][0]) == {"title", "link"}
    for t in plan["tasks"]:
        api.post(f"/today/tasks/{t['id']}/complete/", {"client_id": cid()})
    done = selectors.reminder_digest(USER, day)
    assert done["is_done"] is True and done["open_count"] == 0 and done["top"] == []


def test_a_day_without_a_plan_is_never_done(db):
    digest = selectors.reminder_digest(USER, local_today())
    assert digest["has_plan"] is False and digest["is_done"] is False


# ---- eraser and exporter -------------------------------------------------------------------------------------------------


def test_delete_and_export_cover_every_today_row(api, plan):
    from core import registry as account_registry
    from modules.today import erasure

    assert "today" in dict(account_registry.erasers()) and "today" in dict(account_registry.exporters())
    add_own(api, "Own thing")
    data = erasure.export_for_user(USER)
    assert data["plans"] and data["settings"]["minutes_per_day"] == 240
    assert any(t["title"] == "Own thing" for p in data["plans"] for t in p["tasks"])
    assert json.dumps(data)
    out = erasure.delete_all_for_user(USER)
    assert out["plans"] >= 1 and out["tasks"] >= 1 and out["settings"] == 1
    assert not DayPlan.objects.filter(user_id=USER).exists()
    assert not Task.objects.filter(user_id=USER).exists()
    assert not TodaySettings.objects.filter(pk=USER).exists()
    assert set(erasure.delete_all_for_user(USER).values()) == {0}  # idempotent


# ---- analytics ------------------------------------------------------------------------------------------------------------

SCHEMA = json.loads((Path(analytics.__file__).parent / "domain" / "event_schema.json").read_text())


def test_track_keeps_schema_properties_only_and_never_a_title():
    sent = []
    analytics.set_sink(lambda name, user, props: sent.append((name, props)))
    try:
        analytics.track(
            "today_task_skipped", USER, kind="x", reason="other", suppressed=True, title="Secret", notes="n"
        )
        assert analytics.track("not_an_event", USER, a=1) is None
    finally:
        analytics.set_sink(None)
    assert sent == [("today_task_skipped", {"kind": "x", "reason": "other", "suppressed": True})]
    assert not analytics.NEVER_SENT & {p for e in SCHEMA["events"].values() for p in e["props"]}


def test_domain_events_become_schema_conformant_analytics(api, plan, django_capture_on_commit_callbacks):
    sent = []
    analytics.set_sink(lambda name, user, props: sent.append((name, props)))
    try:
        with django_capture_on_commit_callbacks(execute=True):
            t = plan["tasks"][0]
            api.post(f"/today/tasks/{t['id']}/complete/", {"client_id": cid()})
            api.post(f"/today/tasks/{plan['tasks'][1]['id']}/skip/", {"client_id": cid()})
            lifecycle.close_sweep(after_grace(local_today(), plan["tz"], 1))
    finally:
        analytics.set_sink(None)
    names = {n for n, _ in sent}
    assert {"today_task_completed", "today_task_skipped", "today_day_closed"} <= names
    for name, props in sent:
        assert set(props) <= set(SCHEMA["events"][name]["props"]), name
        assert SCHEMA["events"][name]["where"] == "api"
    completed = next(p for n, p in sent if n == "today_task_completed")
    assert completed["est_minutes_bucket"] in SCHEMA["buckets"]["minutes"] and "est_minutes" not in completed


def test_a_plan_generation_is_announced_with_counts_only(api, enrolled, django_capture_on_commit_callbacks):
    register_practice()
    sent = []
    analytics.set_sink(lambda name, user, props: sent.append((name, props)))
    try:
        with django_capture_on_commit_callbacks(execute=True):
            api.post("/today/open/")
    finally:
        analytics.set_sink(None)
    generated = [p for n, p in sent if n == "today_plan_generated"]
    assert len(generated) == 1
    assert generated[0]["trigger"] == "open" and generated[0]["generation_time_bucket"] in SCHEMA["buckets"]["time"]
    assert set(generated[0]) <= set(SCHEMA["events"]["today_plan_generated"]["props"])


def test_every_event_has_a_place_and_buckets_are_closed_lists():
    assert {e["where"] for e in SCHEMA["events"].values()} == {"web", "api"}
    assert SCHEMA["buckets"]["minutes"][0] == "0-5"
