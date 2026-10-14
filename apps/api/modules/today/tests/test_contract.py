"""
`docs/F-13-API-CONTRACT.md` and the API must say the same thing. The page marks its machine-readable parts with
`<!-- contract:name -->`; this test reads them and compares them with real responses, the URL table and the settings, so a
changed key, a new endpoint or a new error code fails here until the page is updated too.
"""

import re
from datetime import timedelta
from pathlib import Path

import pytest
from django.utils import timezone

from modules.coverage.models import ChapterProgress
from modules.today import errors, urls
from modules.today.models import ProviderConfig
from modules.today.views import TodayView

from .conftest import USER
from .helpers import register_practice

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
    return (timezone.now() + timedelta(days=offset)).date().isoformat()


@pytest.fixture
def opened(api, enrolled):
    """A plan with a backlog notice, so every nested key list can be compared."""
    register_practice()
    ChapterProgress.objects.filter(user_id=USER).update(
        next_revision_due=(timezone.now() - timedelta(days=2)).date(), revision_count=1
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


# ---- errors -----------------------------------------------------------------------------------------------------------------


def test_the_error_table_lists_exactly_the_codes_the_api_can_raise(doc):
    documented = {code: int(http) for code, http, _when in rows(doc, "errors")}
    raised = {
        errors.PlanNotGenerated.default_code: errors.PlanNotGenerated.status_code,
        errors.InvalidDate.default_code: errors.InvalidDate.status_code,
        "feature_disabled": 403,
        "invalid": 400,
    }
    assert documented == raised


def test_each_documented_error_is_what_the_api_really_answers(doc, api, flag, enrolled):
    seen = {
        "plan_not_generated": api.get("/today/plan/"),
        "invalid_date": api.get(f"/today/preview/?date={day(30)}"),
        "invalid": api.put("/today/settings/", {"lite_mode": "max"}),
    }
    flag(False)
    seen["feature_disabled"] = api.get("/today/plan/")
    for code, http, _when in rows(doc, "errors"):
        assert seen[code].status_code == int(http) and seen[code].json_body["error"]["code"] == code
