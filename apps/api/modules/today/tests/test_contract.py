"""
`docs/F-13-API-CONTRACT.md` and the API must say the same thing. The page marks its machine-readable parts with
`<!-- contract:name -->`; this test reads them and compares them with real responses, the URL table and the settings, so a
changed key, a new endpoint or a new error code fails here until the page is updated too.
"""

import re
import uuid
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from modules.coverage.models import ChapterProgress
from modules.today import errors, urls
from modules.today.models import ProviderConfig, Task
from modules.today.registry import KindSpec
from modules.today.views import TodayView

from .conftest import USER
from .helpers import cid, local_today, register_practice

pytestmark = pytest.mark.django_db

DOC = Path(__file__).resolve().parents[5] / "docs" / "F-13-API-CONTRACT.md"


@pytest.fixture(scope="module")
def doc():
    assert DOC.exists(), f"the contract page is missing: {DOC}"
    return DOC.read_text()


def section(doc, name):
    match = re.search(rf"<!-- contract:{name} -->\n(.*?)\n<!-- /contract:{name} -->", doc, re.S) or re.search(
        rf"<!-- contract:{name} -->\n(.*?)\n<!--", doc, re.S
    )
    assert match, f"no <!-- contract:{name} --> block in the contract page"
    return match.group(1).strip()


def keys(doc, name):
    return {k.strip() for k in section(doc, name).split(",") if k.strip()}


def rows(doc, name):
    return [
        [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        for line in section(doc, name).splitlines()
        if line.startswith("|") and not set(line) <= set("| -")
    ][1:]


def day(offset):
    return (local_today() + timedelta(days=offset)).isoformat()


@pytest.fixture
def opened(api, enrolled):
    """A plan with a backlog notice, so every nested key list can be compared."""
    register_practice()
    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=local_today() - timedelta(days=2), revision_count=1
    )
    ProviderConfig.objects.create(provider="coverage.revision", max_candidates=1)
    return api, api.post("/today/open/").json_body


# ---- endpoints and throttles ------------------------------------------------------------------------------------------------


def implemented_endpoints():
    found = {}
    for pattern in urls.urlpatterns:
        view = pattern.callback.view_class
        assert issubclass(view, TodayView)
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view, method):
                found[(method.upper(), str(pattern.pattern))] = view
    return found


def test_the_endpoint_table_lists_exactly_the_implemented_endpoints(doc):
    documented = {(method, path) for method, path, *_ in rows(doc, "endpoints")}
    assert documented == set(implemented_endpoints())


def test_each_endpoint_documents_its_throttle_scope(doc, rf):
    for method, path, _purpose, scope in rows(doc, "endpoints"):
        view = implemented_endpoints()[(method, path)]()
        view.request = rf.generic(method, "/")
        assert view.throttle_scope == scope, f"{method} {path}"


def test_throttle_rates_match_the_page(doc, settings):
    text = doc.split("Throttle scopes:")[1].split("\n")[0]
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    for scope, number, unit in re.findall(r"`(today_\w+)` (\d+) per (minute|day)", text):
        assert rates[scope] == f"{number}/{'min' if unit == 'minute' else 'day'}", scope


# ---- payload keys -----------------------------------------------------------------------------------------------------------


def test_the_plan_payload_has_exactly_the_documented_keys(doc, opened):
    api, open_body = opened
    expected = keys(doc, "plan-keys")
    assert set(open_body) == expected | {"created"}
    plan = api.get("/today/plan/").json_body
    assert set(plan) == expected
    assert set(api.get("/today/plan/?lite=1").json_body) == expected - {"week"}


def test_the_nested_plan_shapes_match(doc, opened):
    api, body = opened
    assert set(body["counts"]) == keys(doc, "counts-keys")
    assert set(body["goal"]) == keys(doc, "goal-keys")
    assert body["backlog"], "the fixture should produce a backlog notice"
    assert set(body["backlog"][0]) == keys(doc, "backlog-keys")
    assert set(body["tiles"][0]) == keys(doc, "tile-keys")
    assert set(body["tasks"][0]) == keys(doc, "task-keys")
    assert set(body["week"][0]) == keys(doc, "week-keys")
    assert set(body["tasks"][0]["why"]) == {"modifiers", "signals"}
    assert set(body["tasks"][0]["link"]) == {"path", "search"}


def test_open_without_a_plan_to_make_has_the_documented_keys(doc, api, scheme):
    assert set(api.post("/today/open/").json_body) == keys(doc, "state-keys")


def test_preview_history_and_settings_have_the_documented_keys(doc, opened):
    api, _ = opened
    preview = api.get(f"/today/preview/?date={day(1)}").json_body
    assert set(preview) == keys(doc, "preview-keys")
    assert preview["tasks"] and set(preview["tasks"][0]) == keys(doc, "preview-task-keys")
    history = api.get("/today/history/").json_body
    assert set(history) == keys(doc, "history-keys")
    assert history["days"] and set(history["days"][0]) == keys(doc, "history-day-keys")
    assert set(api.get("/today/settings/").json_body) == keys(doc, "settings-keys")
    assert set(api.put("/today/settings/", {"celebrate": True}).json_body) == keys(doc, "settings-keys")


# ---- task actions -----------------------------------------------------------------------------------------------------------


def test_every_task_action_answers_the_documented_keys(doc, api, enrolled):
    register_practice()
    plan = api.post("/today/open/").json_body
    task = next(t for t in plan["tasks"] if t["origin"] == "provider")
    base = keys(doc, "task-response-keys")
    extra = {
        action: {k.split("(")[0].strip() for k in text.split(",")} for action, text in rows(doc, "action-extra-keys")
    }

    def check(action, body):
        expected = set(base) | {k for k in extra.get(action, set()) if k}
        if action == "swap":
            expected = (expected - {"task"}) | {"old", "new"}
        assert set(body) == expected, action
        assert set(body["counts"]) == keys(doc, "counts-keys")
        if "task" in body:
            assert set(body["task"]) == keys(doc, "task-keys")

    check("start", api.post(f"/today/tasks/{task['id']}/start/", {"client_id": cid()}).json_body)
    check("complete", api.post(f"/today/tasks/{task['id']}/complete/", {"client_id": cid()}).json_body)
    check("undo", api.post(f"/today/tasks/{task['id']}/undo/", {"client_id": cid(), "from_state": "done"}).json_body)
    check("skip", api.post(f"/today/tasks/{task['id']}/skip/", {"client_id": cid()}).json_body)
    other = next(t for t in plan["tasks"] if t["origin"] == "provider" and t["id"] != task["id"])
    check(
        "snooze", api.post(f"/today/tasks/{other['id']}/snooze/", {"client_id": cid(), "until": "tomorrow"}).json_body
    )
    created = api.post("/today/tasks/", {"client_id": cid(), "title": "Mine", "est_minutes": 5})
    assert created.status_code == 201
    check("add", created.json_body)
    own = created.json_body["task"]
    check("edit", api.patch(f"/today/tasks/{own['id']}/", {"version": own["version"], "title": "Renamed"}).json_body)
    check("delete", api.delete(f"/today/tasks/{own['id']}/").json_body)


def test_swap_and_regenerate_answer_the_documented_keys(doc, api, enrolled):
    from .helpers import candidate, register_fake

    register_practice()
    plan = api.post("/today/open/").json_body
    task = next(t for t in plan["tasks"] if t["origin"] == "provider")
    register_fake(
        "fake.extra",
        [candidate("extra-mcq", "extra_mcq", None, 6, (90, 90, 90, 90))],
        kinds=[KindSpec("extra_mcq", "practice", "mcq", "ListChecks", 6)],
    )
    swap = api.post(f"/today/tasks/{task['id']}/swap/", {"client_id": cid()})
    assert swap.status_code == 200
    assert set(swap.json_body) == (keys(doc, "task-response-keys") - {"task"}) | {"old", "new"}
    regenerated = api.post(
        "/today/plan/regenerate/", {"expected_generation": plan["generation_no"], "client_id": cid()}
    ).json_body
    assert set(regenerated) == keys(doc, "plan-keys") | {"regenerated"}
    assert set(regenerated["regenerated"]) == keys(doc, "regenerated-keys")


# ---- errors -----------------------------------------------------------------------------------------------------------------


def test_the_error_table_lists_exactly_the_codes_the_api_can_raise(doc):
    documented = {code: int(http) for code, http, _when in rows(doc, "errors")}
    raised = {
        cls.default_code: cls.status_code
        for cls in (
            errors.PlanNotGenerated,
            errors.InvalidDate,
            errors.InvalidScope,
            errors.TaskNotFound,
            errors.ProviderTaskReadOnly,
            errors.InvalidTransitionError,
            errors.NoAlternative,
            errors.StateConflict,
            errors.PlanChanged,
            errors.UndoExpiredError,
        )
    }
    raised |= {"feature_disabled": 403, "invalid": 400, "quota_exceeded": 429}
    assert documented == raised


def test_each_documented_error_is_what_the_api_really_answers(doc, api, flag, enrolled):
    from .helpers import candidate, register_fake

    seen = {
        "plan_not_generated": api.get("/today/plan/"),
        "invalid_date": api.get(f"/today/preview/?date={day(30)}"),
        "invalid": api.put("/today/settings/", {"lite_mode": "max"}),
        "invalid_scope": api.post(
            "/today/tasks/", {"client_id": cid(), "title": "x", "est_minutes": 5, "subject_id": str(uuid.uuid4())}
        ),
        "task_not_found": api.post(f"/today/tasks/{uuid.uuid4()}/complete/", {"client_id": cid()}),
    }
    register_practice()
    plan = api.post("/today/open/").json_body
    first, second = [t for t in plan["tasks"] if t["origin"] == "provider"][:2]
    seen["provider_task_readonly"] = api.delete(f"/today/tasks/{first['id']}/")
    seen["invalid_transition"] = api.post(
        f"/today/tasks/{first['id']}/undo/", {"client_id": cid(), "from_state": "done"}
    )
    seen["plan_changed"] = api.post(
        "/today/plan/regenerate/", {"expected_generation": plan["generation_no"] + 5, "client_id": cid()}
    )
    api.post(f"/today/tasks/{first['id']}/complete/", {"client_id": cid()})
    seen["state_conflict"] = api.post(f"/today/tasks/{first['id']}/skip/", {"client_id": cid()})
    Task.objects.filter(pk=first["id"]).update(state_changed_at=timezone.now() - timedelta(seconds=120))
    seen["undo_expired"] = api.post(f"/today/tasks/{first['id']}/undo/", {"client_id": cid(), "from_state": "done"})
    for n in range(20):
        api.post("/today/tasks/", {"client_id": cid(), "title": f"T{n}", "est_minutes": 5})
    seen["quota_exceeded"] = api.post("/today/tasks/", {"client_id": cid(), "title": "21st", "est_minutes": 5})
    # a plan with one suggestion and nothing else to offer
    Task.objects.filter(plan__user_id=USER).exclude(pk=second["id"]).delete()
    from modules.today import registry

    registry.clear()
    register_fake(
        "fake.only", [candidate("only", "only_kind", None, 5)], kinds=[KindSpec("only_kind", "practice", "mcq", "x", 5)]
    )
    Task.objects.filter(pk=second["id"]).update(provider="fake.only", kind="only_kind", dedupe_key="only")
    seen["no_alternative"] = api.post(f"/today/tasks/{second['id']}/swap/", {"client_id": cid()})
    flag(False)
    seen["feature_disabled"] = api.get("/today/plan/")
    for code, http, _when in rows(doc, "errors"):
        assert seen[code].status_code == int(http), code
        assert seen[code].json_body["error"]["code"] == code, code
