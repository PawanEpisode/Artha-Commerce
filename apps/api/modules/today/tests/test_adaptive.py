"""W9 API: day feedback, the adaptive budget suggestion and the bonus round."""

from datetime import timedelta

import pytest

from modules.today.domain import adapt
from modules.today.models import DayFeedback, DayPlan, Task, TodaySettings

from .conftest import USER
from .helpers import cid, local_today, register_many, register_practice

pytestmark = pytest.mark.django_db


# ---- the rule ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("current", "direction", "expected"),
    [
        (60, "too_much", 50),
        (60, "too_little", 70),
        (100, "too_much", 85),
        (15, "too_much", 15),
        (240, "too_little", 240),
    ],
)
def test_the_suggested_minutes(current, direction, expected):
    assert adapt.suggested_minutes(current, direction) == expected


def test_a_suggestion_needs_three_of_the_same_extreme():
    assert adapt.suggestion(["too_much"] * 3, 60) == {"direction": "too_much", "minutes": 50, "current": 60}
    assert adapt.suggestion(["too_little", "too_little", "too_little", "too_much"], 60)["minutes"] == 70
    assert adapt.suggestion(["too_much", "too_much"], 60) is None
    assert adapt.suggestion(["too_much", "just_right", "too_much"], 60) is None
    assert adapt.suggestion(["just_right"] * 3, 60) is None
    assert adapt.suggestion(["too_much"] * 3, 15) is None  # already at the floor: nothing to suggest


# ---- feedback ---------------------------------------------------------------------------------------------------------------


@pytest.fixture
def day(api, enrolled):
    register_practice()
    register_many()
    api.put("/today/settings/", {"minutes_per_day": 60})
    return api.post("/today/open/").json_body


def old_plans(n):
    """`n` earlier days with a plan each, so there are days to answer for."""
    base = DayPlan.objects.get(user_id=USER, local_date=local_today())
    made = []
    for i in range(1, n + 1):
        copy = DayPlan.objects.get(pk=base.pk)
        copy.pk, copy.id, copy.local_date = None, None, local_today() - timedelta(days=i)
        copy._state.adding = True
        import uuid

        copy.id = uuid.uuid4()
        copy.save()
        made.append(copy)
    return made


def test_feedback_is_stored_once_per_day_and_can_change(api, day):
    res = api.post("/today/plan/feedback/", {"rating": "too_much"})
    assert res.status_code == 200 and res.json_body["rating"] == "too_much" and res.json_body["suggestion"] is None
    api.post("/today/plan/feedback/", {"rating": "just_right"})
    assert list(DayFeedback.objects.values_list("rating", flat=True)) == ["just_right"]


def test_feedback_needs_a_plan_a_valid_rating_and_a_recent_date(api, enrolled, day):
    assert api.post("/today/plan/feedback/", {"rating": "meh"}).status_code == 400
    far = (local_today() - timedelta(days=5)).isoformat()
    res = api.post("/today/plan/feedback/", {"rating": "too_much", "date": far})
    assert res.status_code == 400 and res.json_body["error"]["code"] == "invalid_date"
    yesterday = (local_today() - timedelta(days=1)).isoformat()
    res = api.post("/today/plan/feedback/", {"rating": "too_much", "date": yesterday})
    assert res.status_code == 404 and res.json_body["error"]["code"] == "plan_not_generated"


def test_the_feedback_endpoints_need_the_planner_flag(api, day, flag):
    flag(True, planner=False)
    assert api.post("/today/plan/feedback/", {"rating": "too_much"}).status_code == 403
    assert api.get("/today/budget-suggestion/").status_code == 403
    assert api.post("/today/plan/bonus/").status_code == 403


def three_too_much(api):
    plans = old_plans(2)
    for plan in plans:
        api.post("/today/plan/feedback/", {"rating": "too_much", "date": plan.local_date.isoformat()}) if (
            local_today() - plan.local_date
        ).days <= 1 else DayFeedback.objects.create(
            user_id=USER, plan=plan, local_date=plan.local_date, rating="too_much"
        )
    return api.post("/today/plan/feedback/", {"rating": "too_much"}).json_body


def test_three_too_much_in_a_row_suggest_fewer_minutes_and_nothing_changes_yet(api, day):
    body = three_too_much(api)
    assert body["suggestion"] == {"direction": "too_much", "minutes": 50, "current": 60}
    assert api.get("/today/budget-suggestion/").json_body["suggestion"]["minutes"] == 50
    assert api.get("/today/settings/").json_body["minutes_per_day"] == 60


def test_accepting_applies_the_minutes_and_uses_the_answers_up(api, day):
    three_too_much(api)
    res = api.post("/today/budget-suggestion/", {"accept": True})
    assert res.status_code == 200 and res.json_body["suggestion"]["accepted"] is True
    assert TodaySettings.objects.get(pk=USER).minutes_per_day == 50
    assert api.get("/today/budget-suggestion/").json_body["suggestion"] is None
    again = api.post("/today/budget-suggestion/", {"accept": True})
    assert again.status_code == 409 and again.json_body["error"]["code"] == "no_budget_suggestion"


def test_dismissing_keeps_the_minutes_and_does_not_suggest_again(api, day):
    three_too_much(api)
    assert api.post("/today/budget-suggestion/", {"accept": False}).json_body["suggestion"]["accepted"] is False
    assert TodaySettings.objects.get(pk=USER).minutes_per_day == 60
    assert api.get("/today/budget-suggestion/").json_body["suggestion"] is None
    assert DayFeedback.objects.filter(consumed=True).count() == 3


def test_a_student_on_auto_starts_from_the_plans_budget(api, enrolled):
    register_practice()
    api.post("/today/open/")
    budget = DayPlan.objects.get(user_id=USER).budget_minutes
    three_too_much(api)
    assert api.get("/today/budget-suggestion/").json_body["suggestion"]["current"] == budget


def test_another_student_has_no_suggestion(api, day, other_api):
    three_too_much(api)
    assert other_api.get("/today/budget-suggestion/").json_body["suggestion"] is None


# ---- bonus ------------------------------------------------------------------------------------------------------------------


def finish_day(api, body):
    for t in body["tasks"]:
        assert api.post(f"/today/tasks/{t['id']}/complete/", {"client_id": cid()}).status_code == 200


def test_a_day_that_is_not_complete_has_no_bonus(api, day):
    res = api.post("/today/plan/bonus/")
    assert res.status_code == 409 and res.json_body["error"]["details"]["reason"] == "day_not_complete"


def test_a_completed_day_gets_a_small_bonus_that_never_counts(api, enrolled):
    register_practice()
    register_many()
    api.put("/today/settings/", {"minutes_per_day": 30})
    body = api.post("/today/open/").json_body
    finish_day(api, body)
    before = api.get("/today/plan/").json_body
    res = api.post("/today/plan/bonus/")
    assert res.status_code == 200, res.json_body
    added = res.json_body["bonus"]["added"]
    bonus = [t for t in res.json_body["tasks"] if t["is_bonus"]]
    assert 1 <= added <= 3 and len(bonus) == added and sum(t["est_minutes"] for t in bonus) <= 20
    assert res.json_body["counts"] == before["counts"]  # the day, the ring and the streak are untouched
    assert all(not t["is_bonus"] for t in before["tasks"])
    assert Task.objects.filter(plan__user_id=USER, counts_toward_day=False).count() == added
    # finishing a bonus task changes no counter either
    api.post(f"/today/tasks/{bonus[0]['id']}/complete/", {"client_id": cid()})
    assert api.get("/today/plan/").json_body["counts"] == before["counts"]


def test_the_bonus_can_be_used_once_a_day(api, enrolled):
    register_practice()
    register_many()
    api.put("/today/settings/", {"minutes_per_day": 30})
    finish_day(api, api.post("/today/open/").json_body)
    assert api.post("/today/plan/bonus/").status_code == 200
    res = api.post("/today/plan/bonus/")
    assert res.status_code == 409 and res.json_body["error"]["details"]["reason"] == "already_used"
