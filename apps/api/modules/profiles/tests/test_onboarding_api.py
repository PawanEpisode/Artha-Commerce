"""Onboarding endpoints: steps saved through the owning modules, resume, skip, complete, versions and flags."""

import pytest

from modules.coverage.models import CoverageSettings, Enrollment
from modules.profiles.domain.onboarding import ONBOARDING_VERSION
from modules.profiles.models import Onboarding
from modules.profiles.tests.conftest import USER
from modules.tracking.models import Goal

pytestmark = pytest.mark.django_db

STEPS = "/me/onboarding/steps"


def state(api):
    return api.get("/me/onboarding/").json_body


def save(api, key, body):
    return api.put(f"{STEPS}/{key}/", body)


def finish_mandatory(api, ids):
    assert save(api, "profile", {"full_name": "Aarav Mehta"}).status_code == 200
    assert save(api, "course", {"scheme": ids["scheme"], "target_term": ids["term"]}).status_code == 200
    assert save(api, "hours", {"daily_minutes": 150}).status_code == 200
    assert save(api, "targets", {"practice_sets": 2, "revisions": 2, "mocks": 2}).status_code == 200


def test_the_step_list_starts_with_the_mandatory_steps_to_do(api):
    body = state(api)
    assert body["status"] == "not_started" and body["mode"] == "full"
    by_key = {s["key"]: s for s in body["steps"]}
    assert [s["key"] for s in body["steps"]] == ["profile", "course", "hours", "targets", "catchup", "avatar", "alerts"]
    assert (
        by_key["alerts"]["available"] is False
    )  # hidden until the notifications UI is on (see test_onboarding_alerts)
    assert by_key["profile"] == {"key": "profile", "state": "todo", "mandatory": True, "available": True}
    assert by_key["avatar"]["mandatory"] is False
    assert "coaching" not in by_key  # hidden until F-12 registers it, not stubbed


def test_walking_the_whole_flow_through_the_owning_modules(api, ids):
    res = save(api, "profile", {"full_name": "  Aarav  Mehta "})
    assert (
        res.status_code == 200 and res.json_body["status"] == "in_progress" and res.json_body["next_step"] == "course"
    )

    res = save(api, "course", {"scheme": ids["scheme"], "target_term": ids["term"], "exam_date": "2027-05-02"})
    assert res.status_code == 200 and res.json_body["next_step"] == "hours"
    enrollment = Enrollment.objects.get(user_id=USER)
    assert str(enrollment.scheme_id) == ids["scheme"] and str(enrollment.exam_date) == "2027-05-02"

    res = save(api, "hours", {"daily_minutes": 150})
    assert res.status_code == 200 and res.json_body["next_step"] == "targets"
    assert Enrollment.objects.get(user_id=USER).daily_minutes == 150
    assert Goal.objects.filter(user_id=USER, period="daily", target_minutes=150).count() == 1  # "Use as my daily goal"

    res = save(api, "targets", {"practice_sets": 2, "revisions": 2, "mocks": 2})
    assert res.status_code == 200 and res.json_body["missing"] == [] and res.json_body["next_step"] == "catchup"
    settings = CoverageSettings.objects.get(pk=USER)
    assert (settings.targets_preset, settings.targets_confirmed_at is not None) == ("standard", True)

    assert api.post("/me/onboarding/steps/catchup/skip/").json_body["next_step"] == "avatar"
    api.post("/me/onboarding/steps/avatar/skip/")

    done = api.post("/me/onboarding/complete/")
    assert done.status_code == 200 and done.json_body["destination"] == "/app"
    assert done.json_body["state"]["status"] == "completed"
    assert api.get("/me/").json_body["onboarding"]["status"] == "completed"
    row = Onboarding.objects.get(pk=USER)
    assert row.completed_version == ONBOARDING_VERSION and row.completed_at is not None and row.started_at is not None


def test_completing_before_the_mandatory_steps_are_done_lists_what_is_missing(api, ids):
    save(api, "profile", {"full_name": "Aarav"})
    res = api.post("/me/onboarding/complete/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "onboarding_incomplete"
    assert res.json_body["error"]["details"] == {"missing": ["course", "hours", "targets"]}
    assert Onboarding.objects.get(pk=USER).completed_version == 0


def test_completing_twice_is_idempotent(api, ids):
    finish_mandatory(api, ids)
    first = api.post("/me/onboarding/complete/")
    again = api.post("/me/onboarding/complete/")
    assert first.status_code == again.status_code == 200
    assert first.json_body["state"]["status"] == again.json_body["state"]["status"] == "completed"
    assert Onboarding.objects.get(pk=USER).completed_version == ONBOARDING_VERSION


def test_saving_the_same_step_twice_returns_the_same_state_with_one_effect(api, ids):
    first = save(api, "profile", {"full_name": "Aarav"})
    again = save(api, "profile", {"full_name": "Aarav"})
    assert first.json_body == again.json_body
    save(api, "course", {"scheme": ids["scheme"]})
    save(api, "course", {"scheme": ids["scheme"]})
    assert Enrollment.objects.filter(user_id=USER).count() == 1


def test_a_closed_tab_resumes_on_the_first_unfinished_step_with_the_answers_kept(api, ids):
    save(api, "profile", {"full_name": "Neha"})
    save(api, "course", {"scheme": ids["scheme"]})
    body = state(api)  # a later session
    assert body["next_step"] == "hours" and body["status"] == "in_progress"
    assert api.get("/me/").json_body["full_name"] == "Neha"
    assert Onboarding.objects.get(pk=USER).current_step == "course"


def test_editing_the_course_step_again_updates_the_term_and_date_in_place(api, ids):
    save(api, "course", {"scheme": ids["scheme"]})
    save(api, "course", {"scheme": ids["scheme"], "target_term": ids["term"], "exam_date": "2027-06-01"})
    enrollment = Enrollment.objects.get(user_id=USER)
    assert str(enrollment.target_term_id) == ids["term"] and str(enrollment.exam_date) == "2027-06-01"


def test_a_term_from_another_level_is_refused(api, ids):
    from modules.syllabus.models import ExamTerm

    foundation = str(ExamTerm.objects.get(level__course__code="ca", level__code="foundation", code="2027-01").id)
    save(api, "course", {"scheme": ids["scheme"]})
    res = save(api, "course", {"scheme": ids["scheme"], "target_term": foundation})
    assert res.status_code == 400


def test_an_unknown_scheme_is_a_clean_404(api):
    res = save(api, "course", {"scheme": "00000000-0000-4000-8000-000000000000"})
    assert res.status_code == 404


def test_hours_before_the_course_are_refused(api):
    res = save(api, "hours", {"daily_minutes": 120})
    assert res.status_code == 400


@pytest.mark.parametrize("minutes", [14, 961])
def test_hours_outside_15_minutes_to_16_hours_are_refused(api, ids, minutes):
    save(api, "course", {"scheme": ids["scheme"]})
    assert save(api, "hours", {"daily_minutes": minutes}).status_code == 400


def test_the_hours_step_never_overwrites_a_goal_the_student_already_has(api, ids):
    from modules.tracking import services as tracking

    tracking.set_goals(USER, [{"period": "daily", "target_minutes": 45}])
    save(api, "course", {"scheme": ids["scheme"]})
    save(api, "hours", {"daily_minutes": 180})
    assert list(Goal.objects.filter(user_id=USER, period="daily").values_list("target_minutes", flat=True)) == [45]


def test_untick_use_as_goal_sets_no_goal(api, ids):
    save(api, "course", {"scheme": ids["scheme"]})
    save(api, "hours", {"daily_minutes": 180, "use_as_goal": False})
    assert not Goal.objects.filter(user_id=USER).exists()


@pytest.mark.parametrize("bad", [{"practice_sets": 11, "revisions": 1, "mocks": 1}, {"practice_sets": 1}])
def test_targets_must_be_three_numbers_from_zero_to_ten(api, bad):
    assert save(api, "targets", bad).status_code == 400


def test_a_name_that_breaks_the_rules_is_a_field_error(api):
    res = save(api, "profile", {"full_name": "x‮y"})
    assert res.status_code == 400 and "full_name" in res.json_body["error"]["details"]


def test_catchup_marks_the_chosen_chapters_and_is_optional(api, ids):
    from modules.syllabus.models import Chapter

    save(api, "course", {"scheme": ids["scheme"]})
    chapter = str(Chapter.objects.get(key="gst-itc").id)
    res = save(api, "catchup", {"chapter_ids": [chapter]})
    assert res.status_code == 200
    assert api.get(f"/coverage/chapters/{chapter}/").json_body["chapter"]["coverage_pct"] > 0
    assert {s["key"]: s["state"] for s in res.json_body["steps"]}["catchup"] == "done"


def test_mandatory_steps_cannot_be_skipped_and_unknown_steps_are_404(api):
    res = api.post("/me/onboarding/steps/hours/skip/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "step_mandatory"
    assert api.post("/me/onboarding/steps/nope/skip/").status_code == 404
    assert save(api, "nope", {}).status_code == 404


def test_a_skipped_optional_step_is_remembered_and_reported(api):
    res = api.post("/me/onboarding/steps/avatar/skip/")
    assert {s["key"]: s["state"] for s in res.json_body["steps"]}["avatar"] == "skipped"


def test_onboarding_is_private_to_each_student(api, other_api, ids):
    save(api, "profile", {"full_name": "Aarav"})
    assert state(other_api)["next_step"] == "profile"


# --- existing students (backfilled) and version bumps ------------------------------------------


def test_a_backfilled_student_sees_only_the_missing_steps_as_an_update(api, ids):
    api.get("/me/")
    save(api, "course", {"scheme": ids["scheme"]})
    Onboarding.objects.filter(pk=USER).update(completed_version=1, completed_at="2026-10-01T00:00:00Z", backfilled=True)
    body = api.get("/me/").json_body["onboarding"]
    assert body["mode"] == "update" and body["completed_version"] == 1
    assert body["missing"] == ["profile", "hours", "targets"] and body["next_step"] == "profile"


def test_when_everything_is_satisfied_but_the_version_is_behind_the_web_can_complete_silently(api, ids):
    finish_mandatory(api, ids)
    Onboarding.objects.filter(pk=USER).update(completed_version=1, completed_at="2026-10-01T00:00:00Z")
    body = api.get("/me/").json_body["onboarding"]
    assert body["status"] == "in_progress" and body["missing"] == [] and body["next_step"] is None
    assert api.post("/me/onboarding/complete/").json_body["state"]["status"] == "completed"


# --- flags ---------------------------------------------------------------------------------------


def test_with_personalization_off_the_writes_are_403_but_the_bootstrap_still_reads(api, flag_off):
    flag_off("personalization")
    assert api.get("/me/").status_code == 200
    assert api.get("/me/onboarding/").status_code == 200
    for res in (save(api, "profile", {"full_name": "A"}), api.post("/me/onboarding/complete/")):
        assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"
    assert api.patch("/me/", {"full_name": "Aarav"}).status_code == 200  # the profile itself is not flagged


def test_with_study_targets_off_the_targets_step_is_hidden_and_never_blocks_completion(api, ids, flag_off):
    flag_off("study_targets")
    body = state(api)
    assert {s["key"]: s["available"] for s in body["steps"]}["targets"] is False
    assert "targets" not in body["missing"]
    assert save(api, "targets", {"practice_sets": 1, "revisions": 1, "mocks": 1}).status_code == 404
    save(api, "profile", {"full_name": "Aarav"})
    save(api, "course", {"scheme": ids["scheme"]})
    save(api, "hours", {"daily_minutes": 120})
    assert api.post("/me/onboarding/complete/").status_code == 200


def test_domain_events_fire_after_completion(api, ids, django_capture_on_commit_callbacks):
    from core import events

    seen = []
    events.clear()
    events.subscribe("onboarding_completed", lambda **p: seen.append(p))
    try:
        finish_mandatory(api, ids)
        with django_capture_on_commit_callbacks(execute=True):
            api.post("/me/onboarding/complete/")
        with django_capture_on_commit_callbacks(execute=True):
            api.post("/me/onboarding/complete/")  # idempotent: no second event
    finally:
        events.clear()
    assert len(seen) == 1 and seen[0]["version"] == ONBOARDING_VERSION and seen[0]["course"] == "ca"
