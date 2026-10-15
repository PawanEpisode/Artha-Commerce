"""POST plan/celebrated/ and the `closing` and `budget_source` plan fields (W5)."""

import pytest

from modules.today.models import DayPlan

from .conftest import USER
from .helpers import cid, local_today, register_many, register_practice

pytestmark = pytest.mark.django_db


@pytest.fixture
def plan(api, enrolled):
    register_practice()
    register_many()
    api.put("/today/settings/", {"minutes_per_day": 240})
    return api.post("/today/open/").json_body


def test_no_plan_is_404(api, enrolled):
    res = api.post("/today/plan/celebrated/", {})
    assert res.status_code == 404
    assert res.json_body["error"]["code"] == "plan_not_generated"


def test_plan_carries_budget_source_and_an_open_closing(plan):
    assert plan["budget_source"] in {"auto", "setting", "comeback", "feedback"}
    assert plan["closing"] is None
    assert plan["celebrate"] is False


def test_celebrate_once_across_devices(api, plan):
    for task in plan["tasks"]:
        api.post(f"/today/tasks/{task['id']}/complete/", {"client_id": cid()})
    again = api.post("/today/open/").json_body
    assert again["closing"] == "celebrate"
    assert again["celebrate"] is True

    first = api.post("/today/plan/celebrated/", {})
    assert first.status_code == 200
    stamp = first.json_body["celebrated_at"]
    assert api.post("/today/plan/celebrated/", {}).json_body["celebrated_at"] == stamp  # a replay changes nothing

    after = api.post("/today/open/").json_body
    assert after["celebrate"] is False
    assert after["closing"] == "celebrate"
    assert DayPlan.objects.get(user_id=USER, local_date=local_today()).celebrated_at is not None


def test_mostly_skipped_day_closes_calm_without_celebration(api, plan):
    tasks = plan["tasks"]
    assert len(tasks) >= 3
    api.post(f"/today/tasks/{tasks[0]['id']}/complete/", {"client_id": cid()})
    for task in tasks[1:]:
        api.post(f"/today/tasks/{task['id']}/skip/", {"client_id": cid()})
    after = api.post("/today/open/").json_body
    assert after["closing"] == "calm"
    assert after["celebrate"] is False
