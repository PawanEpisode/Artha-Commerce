"""
F-16 S2: the student's own study targets. Presets, validation, the recompute that never edits history, the
dry-run impact, the flag, idempotency and the daily study time that moved from decimal hours to minutes.
"""

import json
import uuid
from pathlib import Path

import pytest
from django.apps import apps
from django.core.management import call_command

from core import events, feature_flags
from modules.coverage import selectors
from modules.coverage.domain import targets
from modules.coverage.models import ChapterProgress, CoverageEvent, CoverageSettings, Enrollment
from modules.coverage.tests.conftest import USER

CASES = json.loads((Path(__file__).parent / "fixtures" / "rules_cases.json").read_text())

pytestmark = pytest.mark.django_db


# --- pure rules ------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES["preset_for"], ids=lambda c: c["name"])
def test_preset_is_derived_from_the_numbers(case):
    assert targets.preset_for(targets.Targets(*case["targets"])) == case["expected"]


@pytest.mark.parametrize("case", CASES["direction_of"], ids=lambda c: c["name"])
def test_direction_of_a_change(case):
    assert targets.direction_of(targets.Targets(*case["old"]), targets.Targets(*case["new"])) == case["expected"]


def test_impact_counts_only_chapters_that_moved():
    impact = targets.impact_of([(40, 40), (60, 50), (20, 35), (100, 100), (10, 0)])
    assert (impact.chapters_changed, impact.chapters_dropping, impact.chapters_rising) == (3, 2, 1)


def test_targets_outside_zero_to_ten_are_invalid():
    assert targets.targets_valid(targets.Targets(0, 10, 5))
    assert not targets.targets_valid(targets.Targets(11, 1, 1))
    assert not targets.targets_valid(targets.Targets(1, -1, 1))


# --- reading and writing targets -------------------------------------------------------------


def put_targets(api, practice_sets, revisions, mocks, **extra):
    return api.put(
        "/coverage/settings/",
        {"targets": {"practice_sets": practice_sets, "revisions": revisions, "mocks": mocks}, **extra},
    )


def chapter(api, ids):
    return api.get(f"/coverage/chapters/{ids['gst']}/").json_body["chapter"]


def test_a_new_student_sees_the_pre_f16_defaults_unconfirmed_with_the_preset_table(api):
    body = api.get("/coverage/settings/").json_body
    assert body["targets"] == {"practice_sets": 1, "revisions": 2, "mocks": 1}
    assert body["targets_preset"] == "custom" and body["targets_confirmed"] is False
    assert body["targets_version"] == 1
    assert [p["key"] for p in body["target_presets"]] == ["light", "standard", "intense"]
    assert body["target_presets"][1] == {
        "key": "standard",
        "label": "Standard",
        "practice_sets": 2,
        "revisions": 2,
        "mocks": 2,
    }
    assert body["target_limits"] == {"min": 0, "max": 10}


def test_saving_targets_confirms_them_and_derives_the_preset(api):
    res = put_targets(api, 2, 2, 2, preset="intense")  # the advisory preset is ignored: the numbers decide
    body = res.json_body
    assert res.status_code == 200
    assert body["targets"] == {"practice_sets": 2, "revisions": 2, "mocks": 2}
    assert body["targets_preset"] == "standard" and body["targets_confirmed"] is True
    assert body["targets_version"] == 2
    assert put_targets(api, 2, 3, 3).json_body["targets_preset"] == "custom"


def test_saving_the_same_targets_again_changes_nothing_but_records_the_confirmation(api):
    first = put_targets(api, 1, 2, 1).json_body  # the defaults, confirmed by the student
    assert first["targets_version"] == 1 and first["targets_confirmed"] is True
    again = put_targets(api, 1, 2, 1).json_body
    assert again["targets_version"] == 1 and again["impact"]["chapters_changed"] == 0


@pytest.mark.parametrize("bad", [(11, 1, 1), (1, -1, 1), (1, 1, 99)])
def test_targets_outside_the_range_are_refused(api, bad):
    res = put_targets(api, *bad)
    assert res.status_code == 400
    assert api.get("/coverage/settings/").json_body["targets_confirmed"] is False  # nothing was saved


def test_targets_need_all_three_numbers(api):
    res = api.put("/coverage/settings/", {"targets": {"practice_sets": 2}})
    assert res.status_code == 400


def test_an_empty_settings_body_is_refused(api):
    assert api.put("/coverage/settings/", {}).status_code == 400


def test_weights_and_revision_gaps_must_come_together(api):
    res = api.put("/coverage/settings/", {"w_read": 40, "w_practice": 30})
    assert res.status_code == 400 and "w_revise" in res.json_body["error"]["details"]


def test_saving_only_targets_leaves_weights_and_revision_gaps_alone(api):
    api.put(
        "/coverage/settings/",
        {"w_read": 70, "w_practice": 10, "w_revise": 10, "w_mock": 10, "revision_days": [2, 5]},
    )
    put_targets(api, 3, 3, 3)
    body = api.get("/coverage/settings/").json_body
    assert (body["w_read"], body["revision_days"]) == (70, [2, 5])


def test_resetting_weights_keeps_the_students_targets(api):
    put_targets(api, 3, 3, 3)
    body = api.delete("/coverage/settings/").json_body
    assert body["w_read"] == 40 and body["targets"] == {"practice_sets": 3, "revisions": 3, "mocks": 3}


def test_targets_are_private_to_each_student(api, other_api):
    put_targets(api, 3, 3, 3)
    assert other_api.get("/coverage/settings/").json_body["targets"] == {"practice_sets": 1, "revisions": 2, "mocks": 1}


# --- the formula and the cap use the student's targets ---------------------------------------


def test_every_chapter_shows_the_students_targets_as_denominators(api, ids, enrolled):
    put_targets(api, 4, 3, 5)
    row = chapter(api, ids)
    assert row["targets"] == {"practice": 4, "revisions": 3, "mocks": 5}
    assert row["activities"]["mocks"]["target"] == 5


def test_the_cap_follows_the_students_target_not_the_syllabus_columns(api, ids, enrolled):
    put_targets(api, 2, 2, 3)
    for _ in range(3):
        assert api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "mock_done"}).status_code == 201
    res = api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "mock_done"})
    assert res.status_code == 409 and res.json_body["error"]["details"]["target"] == 3


def test_lowering_targets_never_edits_history_and_can_only_raise_percentages(api, ids, enrolled):
    put_targets(api, 2, 2, 3)
    for _ in range(3):
        api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "mock_done"})
    before = chapter(api, ids)
    assert before["activities"]["mocks"] == {"done": 3, "target": 3, "logged": 3, "can_log": False}

    res = put_targets(api, 2, 2, 2)
    after = chapter(api, ids)
    assert after["mock_count"] == 3  # the fact is kept
    assert after["activities"]["mocks"] == {"done": 2, "target": 2, "logged": 3, "can_log": False}
    assert after["components"]["mock"] == 100
    assert after["coverage_pct"] >= before["coverage_pct"]
    assert res.json_body["impact"]["chapters_dropping"] == 0
    assert CoverageEvent.objects.filter(type="mock_done").count() == 3  # the ledger is untouched


def test_raising_targets_lowers_percentages_and_reopens_logging(api, ids, enrolled):
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "mock_done"})  # 1 of 1 mocks
    before = chapter(api, ids)
    assert before["components"]["mock"] == 100 and before["activities"]["mocks"]["can_log"] is False

    res = put_targets(api, 2, 2, 4)
    after = chapter(api, ids)
    assert after["components"]["mock"] == 25 and after["coverage_pct"] < before["coverage_pct"]
    assert after["activities"]["mocks"]["can_log"] is True
    assert res.json_body["impact"]["chapters_dropping"] == 1


def test_a_target_of_zero_hides_the_part_and_redistributes_its_weight(api, ids, enrolled):
    api.post("/coverage/catchup/", {"chapter_ids": [ids["gst"]]})  # read 100, nothing else
    with_mocks = chapter(api, ids)["coverage_pct"]
    put_targets(api, 2, 2, 0)
    row = chapter(api, ids)
    assert with_mocks == 40  # read 100 at weight 40 of 100
    assert row["coverage_pct"] == 44  # mocks drop out: 40 of the remaining 90 points of weight
    assert row["activities"]["mocks"]["can_log"] is False
    res = api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "mock_done"})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "activity_not_tracked"


def test_a_rebuild_from_the_ledger_matches_the_live_numbers_with_custom_targets(api, ids, enrolled):
    put_targets(api, 3, 1, 2)
    for kind in ("practice_done", "practice_done", "mock_done"):
        api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": kind})
    live = list(ChapterProgress.objects.order_by("chapter_id").values_list("chapter_id", "coverage_pct", "status"))
    call_command("rebuild_coverage")
    rebuilt = list(ChapterProgress.objects.order_by("chapter_id").values_list("chapter_id", "coverage_pct", "status"))
    assert rebuilt == live


# --- dry run ---------------------------------------------------------------------------------


def test_preview_reports_the_impact_and_writes_nothing(api, ids, enrolled):
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "mock_done"})
    stored = list(ChapterProgress.objects.values_list("id", "coverage_pct"))
    version = CoverageSettings.objects.get(pk=USER).targets_version

    res = api.post("/coverage/settings/targets/preview/", {"practice_sets": 2, "revisions": 2, "mocks": 4})
    assert res.status_code == 200
    assert res.json_body == {"chapters_changed": 1, "chapters_dropping": 1, "chapters_rising": 0}
    assert list(ChapterProgress.objects.values_list("id", "coverage_pct")) == stored
    assert CoverageSettings.objects.get(pk=USER).targets_version == version


def test_preview_validates_its_input(api, enrolled):
    assert (
        api.post("/coverage/settings/targets/preview/", {"practice_sets": 99, "revisions": 1, "mocks": 1}).status_code
        == 400
    )


# --- flag and events -------------------------------------------------------------------------


@pytest.fixture
def targets_flag_off(settings, monkeypatch):
    class Off:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key == "study_targets" else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Off())
    feature_flags.clear_flag_cache()
    yield
    feature_flags.clear_flag_cache()


def test_with_the_flag_off_targets_can_be_read_but_not_changed_and_weights_still_save(api, targets_flag_off):
    assert api.get("/coverage/settings/").status_code == 200
    res = put_targets(api, 3, 3, 3)
    assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"
    weights = {"w_read": 50, "w_practice": 20, "w_revise": 20, "w_mock": 10, "revision_days": [3, 7]}
    assert api.put("/coverage/settings/", weights).status_code == 200


def test_a_change_announces_study_targets_changed_after_commit(api, django_capture_on_commit_callbacks):
    seen: list[dict] = []
    events.clear()
    events.subscribe("study_targets_changed", lambda **payload: seen.append(payload))
    try:
        with django_capture_on_commit_callbacks(execute=True):
            put_targets(api, 3, 3, 3)
        with django_capture_on_commit_callbacks(execute=True):
            put_targets(api, 3, 3, 3)  # same numbers: nothing to announce
    finally:
        events.clear()
    assert len(seen) == 1
    assert seen[0]["user_id"] == USER and seen[0]["version"] == 2
    assert seen[0]["new"] == targets.Targets(3, 3, 3) and str(seen[0]["direction"]) == "raised"


def test_a_failing_subscriber_never_breaks_the_save(api, django_capture_on_commit_callbacks):
    events.clear()

    def boom(**_):
        raise RuntimeError("consumer bug")

    events.subscribe("study_targets_changed", boom)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            res = put_targets(api, 3, 3, 3)
    finally:
        events.clear()
    assert res.status_code == 200 and selectors.get_targets(USER) == targets.Targets(3, 3, 3)


def test_get_targets_defaults_without_creating_a_row(db):
    assert selectors.get_targets(uuid.uuid4()) == targets.DEFAULT_TARGETS
    assert CoverageSettings.objects.count() == 0


# --- daily study time ------------------------------------------------------------------------


def test_enrolment_stores_daily_minutes_and_mirrors_hours(api, ids):
    res = api.post(
        "/coverage/enrollments/", {"scheme": ids["scheme"], "target_term": ids["term"], "daily_minutes": 150}
    )
    assert res.status_code == 201
    assert res.json_body["daily_minutes"] == 150 and res.json_body["daily_hours"] == 2.5


def test_a_legacy_client_sending_decimal_hours_is_converted_and_only_minutes_are_stored(api, enrolled):
    res = api.patch(f"/coverage/enrollments/{enrolled['id']}/", {"daily_hours": "4.5"})
    assert res.status_code == 200 and res.json_body["daily_minutes"] == 270
    stored = Enrollment.objects.get(pk=enrolled["id"])
    assert stored.daily_minutes == 270 and stored.daily_hours is None


@pytest.mark.parametrize("minutes", [14, 961, 0, -5])
def test_daily_minutes_outside_15_to_960_are_refused(api, enrolled, minutes):
    assert api.patch(f"/coverage/enrollments/{enrolled['id']}/", {"daily_minutes": minutes}).status_code == 400


def test_daily_minutes_can_be_cleared(api, enrolled):
    api.patch(f"/coverage/enrollments/{enrolled['id']}/", {"daily_minutes": 90})
    res = api.patch(f"/coverage/enrollments/{enrolled['id']}/", {"daily_minutes": None})
    assert res.status_code == 200 and res.json_body["daily_minutes"] is None


def test_legacy_decimal_hours_still_read_as_minutes():
    legacy = Enrollment(daily_hours="2.5")
    assert legacy.planned_minutes == 150 and Enrollment().planned_minutes is None
    assert Enrollment(daily_hours="2.5", daily_minutes=200).planned_minutes == 200


def test_the_backfill_turns_legacy_hours_into_minutes(api, enrolled):
    Enrollment.objects.filter(pk=enrolled["id"]).update(daily_hours="3.5", daily_minutes=None)
    from importlib import import_module

    import_module("modules.coverage.migrations.0004_study_targets_and_daily_minutes").backfill_daily_minutes(apps, None)
    assert Enrollment.objects.get(pk=enrolled["id"]).daily_minutes == 210
