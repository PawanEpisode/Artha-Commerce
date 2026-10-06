"""The `alerts` onboarding step (X-01.1 W2.5): registered by profiles, facts from the notifications selector."""

import pytest
from cryptography.fernet import Fernet

from modules.profiles.domain.onboarding import ONBOARDING_VERSION
from modules.profiles.models import Onboarding
from modules.profiles.tests.conftest import USER
from modules.profiles.tests.test_onboarding_api import finish_mandatory, save, state

pytestmark = pytest.mark.django_db

PERMISSION = "/notifications/permission-state/"


@pytest.fixture
def alerts_on(settings):
    """Environment switch on; PostHog is unconfigured, so the web-visible flags fail open."""
    settings.NOTIFICATIONS_ENABLED = True
    settings.FIELD_ENCRYPTION_KEYS = [Fernet.generate_key().decode()]
    settings.FIELD_HASH_PEPPER = "pepper-pepper-pepper"


def step(api, key="alerts"):
    return next(s for s in state(api)["steps"] if s["key"] == key)


def decide(api, result="dismissed"):
    res = api.post(PERMISSION, {"state": result, "source": "onboarding"})
    assert res.status_code == 200
    return res


def test_the_step_is_hidden_while_the_environment_switch_is_off(api, ids):
    assert step(api)["available"] is False
    finish_mandatory(api, ids)
    for key in ("catchup", "avatar"):
        api.post(f"/me/onboarding/steps/{key}/skip/")
    body = state(api)
    assert body["next_step"] is None and "alerts" not in body["missing"]
    assert save(api, "alerts", {}).status_code == 404  # a hidden step cannot be saved
    assert api.post("/me/onboarding/steps/alerts/skip/").status_code == 404
    assert api.post("/me/onboarding/complete/").status_code == 200  # and never blocks completion


def test_the_step_is_hidden_when_the_notifications_ui_flag_is_off(api, alerts_on, flag_off):
    flag_off("notifications_ui")
    assert step(api)["available"] is False


def test_the_step_is_optional_and_comes_last_for_a_new_student(api, ids, alerts_on):
    assert step(api) == {"key": "alerts", "state": "todo", "mandatory": False, "available": True}
    assert [s["key"] for s in state(api)["steps"]][-1] == "alerts"
    finish_mandatory(api, ids)
    api.post("/me/onboarding/steps/catchup/skip/")
    assert state(api)["next_step"] == "avatar"
    api.post("/me/onboarding/steps/avatar/skip/")
    body = state(api)
    assert body["next_step"] == "alerts" and body["missing"] == []  # optional: never blocks, but is offered once


def test_the_step_cannot_be_saved_before_a_decision_is_recorded(api, alerts_on):
    res = save(api, "alerts", {})
    assert res.status_code == 400 and "Choose an option" in res.json_body["error"]["message"]
    assert step(api)["state"] == "todo"


@pytest.mark.parametrize("result", ["granted", "denied", "dismissed", "skipped_install", "unsupported"])
def test_every_decided_outcome_finishes_the_step_from_the_facts(api, alerts_on, result):
    decide(api, result)
    assert step(api)["state"] == "done"
    assert save(api, "alerts", {}).status_code == 200
    assert save(api, "alerts", {}).status_code == 200  # idempotent


def test_showing_the_pre_prompt_is_not_a_decision_and_the_step_resumes(api, ids, alerts_on):
    decide(api, "pre_prompt_shown")
    assert step(api)["state"] == "todo"  # a refresh lands on the same step
    finish_mandatory(api, ids)
    for key in ("catchup", "avatar"):
        api.post(f"/me/onboarding/steps/{key}/skip/")
    assert state(api)["next_step"] == "alerts"
    assert save(api, "alerts", {}).status_code == 400


def test_the_step_can_be_skipped_and_is_then_reported_as_skipped(api, alerts_on):
    res = api.post("/me/onboarding/steps/alerts/skip/")
    assert {s["key"]: s["state"] for s in res.json_body["steps"]}["alerts"] == "skipped"


def test_a_decision_belongs_to_one_student(api, other_api, alerts_on):
    decide(api, "granted")
    assert step(other_api)["state"] == "todo"


def test_a_student_who_finished_version_two_completes_silently_and_is_not_walked_through_it(api, ids, alerts_on):
    finish_mandatory(api, ids)
    Onboarding.objects.filter(pk=USER).update(completed_version=2, completed_at="2026-10-01T00:00:00Z")
    body = api.get("/me/").json_body["onboarding"]
    assert body["status"] == "in_progress" and body["mode"] == "update" and body["next_step"] is None
    assert api.post("/me/onboarding/complete/").json_body["state"]["status"] == "completed"
    assert Onboarding.objects.get(pk=USER).completed_version == ONBOARDING_VERSION
    assert step(api)["state"] == "todo"  # still offered later, from the setup card and Settings
