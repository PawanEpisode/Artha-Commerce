"""POST plan/regenerate/: what stays, what is replaced, optimistic locking, the daily limit (PRD FR-F13-12)."""

import pytest

from modules.today.models import DayPlan, Task

from .conftest import USER
from .helpers import candidate, cid, local_today, register_fake, register_many, register_practice
from .test_task_actions import reference_counts, stored_counts

pytestmark = pytest.mark.django_db


def regen(api, plan, **over):
    body = {"expected_generation": plan["generation_no"], "reason": "manual", "client_id": cid()}
    body.update(over)
    return api.post("/today/plan/regenerate/", body)


@pytest.fixture
def plan(api, enrolled):
    register_practice()
    register_many()
    api.put(
        "/today/settings/", {"minutes_per_day": 240}
    )  # a long day: five or six suggestions to touch in different ways
    return api.post("/today/open/").json_body


def test_regenerate_keeps_what_the_student_touched_and_replaces_the_rest(api, plan):
    provider = [t for t in plan["tasks"] if t["origin"] == "provider"]
    done, started, skipped, snoozed = provider[:4]
    api.post(f"/today/tasks/{done['id']}/complete/", {"client_id": cid()})
    api.post(f"/today/tasks/{started['id']}/start/", {"client_id": cid()})
    api.post(f"/today/tasks/{skipped['id']}/skip/", {"client_id": cid()})
    api.post(f"/today/tasks/{snoozed['id']}/snooze/", {"client_id": cid(), "until": "tomorrow"})
    own = api.post("/today/tasks/", {"client_id": cid(), "title": "Mine", "est_minutes": 5}).json_body["task"]
    suggested_before = {t["id"] for t in provider[4:]}

    res = regen(api, plan)
    body = res.json_body
    assert res.status_code == 200 and body["generation_no"] == plan["generation_no"] + 1
    states = {t["id"]: t["state"] for t in body["tasks"]}
    assert states[done["id"]] == "done" and states[started["id"]] == "accepted" and states[skipped["id"]] == "skipped"
    assert states[snoozed["id"]] == "snoozed" and states[own["id"]] == "suggested"
    assert not (suggested_before & set(states))  # the old suggestions are gone from the plan
    expired = Task.objects.filter(id__in=suggested_before)
    assert expired.exists() and set(expired.values_list("state", "end_reason")) == {("expired", "regenerated")}
    assert body["regenerated"]["replaced"] == len(suggested_before) and body["regenerated"]["replayed"] is False
    row = DayPlan.objects.get(user_id=USER, local_date=local_today())
    assert stored_counts(row.id) == reference_counts(row.id)


def test_a_skipped_key_is_not_offered_again_by_a_regeneration(api, plan):
    skipped = next(t for t in plan["tasks"] if t["origin"] == "provider")
    key = Task.objects.get(pk=skipped["id"]).dedupe_key
    api.post(f"/today/tasks/{skipped['id']}/skip/", {"client_id": cid()})
    regen(api, plan)
    assert (
        Task.objects.filter(user_id=USER, dedupe_key=key, deleted_at__isnull=True).exclude(state="expired").count() == 1
    )


def test_a_stale_expected_generation_is_409_plan_changed(api, plan):
    res = regen(api, plan, expected_generation=plan["generation_no"] + 3)
    assert res.status_code == 409 and res.json_body["error"]["code"] == "plan_changed"
    assert res.json_body["error"]["details"]["generation_no"] == plan["generation_no"]
    assert DayPlan.objects.get(user_id=USER).generation_no == plan["generation_no"]  # nothing changed


def test_a_retry_with_the_same_client_id_changes_nothing(api, plan):
    c = cid()
    first = regen(api, plan, client_id=c).json_body
    again = regen(api, plan, client_id=c)
    assert again.status_code == 200 and again.json_body["generation_no"] == first["generation_no"]
    assert again.json_body["regenerated"]["replayed"] is True
    assert again.json_body["tasks"] == first["tasks"]


def test_a_second_caller_with_the_same_expectation_loses(api, plan):
    assert regen(api, plan).status_code == 200
    assert regen(api, plan).status_code == 409


def test_six_regenerations_a_day_is_the_limit(api, plan):
    from core.errors import QuotaExceeded
    from modules.today import actions
    from modules.today.errors import PlanChanged  # noqa: F401 - the other 409 this endpoint can answer

    current = plan
    for _ in range(6):
        res = regen(api, current)
        assert res.status_code == 200, res.json_body
        current = res.json_body
    with pytest.raises(QuotaExceeded) as caught:  # the database fact, behind the throttle's politeness
        actions.regenerate(USER, expected_generation=current["generation_no"], reason="manual", client_id=cid())
    assert caught.value.extra == {"kind": "regenerations", "used": 6, "limit": 6}
    assert regen(api, current).status_code == 429  # and over HTTP the seventh call is refused too


def test_no_plan_or_only_a_draft_is_404(api, enrolled):
    assert regen(api, {"generation_no": 1}).status_code == 404
    api.post("/today/tasks/", {"client_id": cid(), "title": "Mine", "est_minutes": 5})
    assert regen(api, {"generation_no": 1}).status_code == 404


def test_a_plan_that_is_already_full_does_not_grow(api, plan):
    for t in plan["tasks"]:
        api.post(
            f"/today/tasks/{t['id']}/start/", {"client_id": cid()}
        )  # everything is under way: nothing is replaceable
    api.put("/today/settings/", {"minutes_per_day": 15})  # the student shortens the day: what stays already fills it
    body = regen(api, plan, reason="settings").json_body
    assert body["counts"]["planned"] == plan["counts"]["planned"] and body["regenerated"]["replaced"] == 0
    assert body["budget_minutes"] == 15


def test_a_plan_below_the_fill_target_gets_new_suggestions_only_up_to_the_cap(api, plan):
    for t in plan["tasks"][:-1]:
        api.post(f"/today/tasks/{t['id']}/start/", {"client_id": cid()})
    body = regen(api, plan).json_body
    assert body["planned_minutes"] <= body["budget_minutes"] * 1.25


def test_new_suggestions_come_after_the_kept_tasks_in_display_order(api, enrolled):
    register_fake("fake.mcq", lambda request: [candidate(f"k{n}", minutes=5) for n in range(3)])
    plan = api.post("/today/open/").json_body
    api.post(f"/today/tasks/{plan['tasks'][0]['id']}/complete/", {"client_id": cid()})
    body = regen(api, plan).json_body
    positions = list(
        Task.objects.filter(plan__user_id=USER)
        .exclude(state="expired")
        .order_by("position")
        .values_list("position", flat=True)
    )
    assert positions == sorted(positions) and len(set(positions)) == len(positions)
    assert body["tasks"][0]["state"] == "done"


def test_regenerate_applies_a_changed_setting(api, plan):
    api.put("/today/settings/", {"disabled_kinds": ["fake_formula"]})
    body = regen(api, plan, reason="settings").json_body
    assert "fake_formula" not in {t["kind"] for t in body["tasks"] if t["state"] == "suggested"}
