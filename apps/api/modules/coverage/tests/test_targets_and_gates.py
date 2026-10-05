"""
F-16 S1: activity targets cap manual logs, confidence unlocks at 50%, and the progress numbers stay honest.
The pure rules share `fixtures/rules_cases.json` with the web mirror (`coverage/lib/rules.ts`).
"""

import json
import threading
import uuid
from pathlib import Path

import pytest
from django.db import connection

from modules.coverage import services
from modules.coverage.domain import targets
from modules.coverage.models import ChapterProgress, CoverageEvent, Enrollment

from .conftest import set_targets

CASES = json.loads((Path(__file__).parent / "fixtures" / "rules_cases.json").read_text())


# --- pure rules ------------------------------------------------------------------------------


@pytest.mark.parametrize("case", CASES["can_log"], ids=[c["name"] for c in CASES["can_log"]])
def test_can_log_matches_shared_fixtures(case):
    assert targets.can_log(count=case["count"], add=case["add"], target=case["target"]) == case["expected"]


@pytest.mark.parametrize("case", CASES["confidence_allowed"], ids=lambda c: str(c["coverage_pct"]))
def test_confidence_allowed_matches_shared_fixtures(case):
    assert targets.confidence_allowed(case["coverage_pct"]) is case["expected"]


@pytest.mark.parametrize("case", CASES["activity_progress"], ids=lambda c: f"{c['count']}-of-{c['target']}")
def test_activity_progress_never_shows_more_than_the_target(case):
    assert targets.activity_progress(case["count"], case["target"]) == case["expected"]


# --- the cap through the API -----------------------------------------------------------------


def log(api, ids, kind, **extra):
    return api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": kind, **extra})


def chapter(api, ids):
    return api.get(f"/coverage/chapters/{ids['gst']}/").json_body["chapter"]


@pytest.mark.django_db
def test_a_manual_log_past_the_target_is_refused_with_a_typed_error(api, ids, enrolled):
    assert log(api, ids, "mock_done", value="40").status_code == 201  # chapter target: 1 mock
    res = log(api, ids, "mock_done", value="45", client_id=str(uuid.uuid4()))
    assert res.status_code == 409
    error = res.json_body["error"]
    assert error["code"] == "target_reached"
    assert error["details"] == {"activity": "mocks", "target": 1, "count": 1}
    assert "Mock tests" in error["message"]
    assert CoverageEvent.objects.filter(type="mock_done").count() == 1  # nothing was written
    assert chapter(api, ids)["mock_count"] == 1


@pytest.mark.django_db
def test_logging_up_to_exactly_the_target_works_and_the_next_one_is_blocked(api, ids, enrolled):
    for expected in (1, 2):  # practice target is 2 on this chapter
        res = log(api, ids, "practice_done")
        assert res.status_code == 201 and res.json_body["chapter"]["activities"]["practice"]["done"] == expected
    assert res.json_body["chapter"]["activities"]["practice"]["can_log"] is False
    assert log(api, ids, "practice_done").status_code == 409
    assert chapter(api, ids)["practice_count"] == 2


@pytest.mark.django_db
def test_replaying_a_client_id_returns_the_original_with_200_even_when_the_cap_is_now_reached(api, ids, enrolled):
    cid = str(uuid.uuid4())
    first = log(api, ids, "mock_done", client_id=cid)
    again = log(api, ids, "mock_done", client_id=cid)  # a retry of the request that took the last slot
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json_body["chapter"]["mock_count"] == 1
    assert CoverageEvent.objects.filter(type="mock_done").count() == 1
    assert log(api, ids, "mock_done", client_id=str(uuid.uuid4())).status_code == 409  # a NEW request is refused


@pytest.mark.django_db
def test_legacy_rows_above_the_target_show_clamped_and_block_more_without_crashing(api, ids, enrolled):
    ChapterProgress.objects.update_or_create(
        user_id=Enrollment.objects.get().user_id, chapter_id=ids["gst"], defaults={"mock_count": 2}
    )
    row = chapter(api, ids)
    assert row["mock_count"] == 2  # the fact is kept
    assert row["activities"]["mocks"] == {"done": 1, "target": 1, "logged": 2, "can_log": False}
    assert log(api, ids, "mock_done").status_code == 409
    assert api.get("/coverage/overview/").status_code == 200


@pytest.mark.django_db
def test_a_target_of_zero_means_the_activity_is_not_tracked(api, ids, enrolled):
    set_targets(api, practice_sets=2, revisions=2, mocks=0)
    res = log(api, ids, "mock_done")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "activity_not_tracked"
    assert chapter(api, ids)["activities"]["mocks"]["can_log"] is False


@pytest.mark.django_db
def test_events_from_other_modules_are_facts_and_are_never_refused(api, ids, enrolled):
    user_id = Enrollment.objects.get().user_id
    log(api, ids, "mock_done")  # at target now
    services.record_event(user_id, ids["gst"], "mock_done", 80, "question_bank", uuid.uuid4())
    row = chapter(api, ids)
    assert row["mock_count"] == 2 and row["activities"]["mocks"]["done"] == 1
    assert row["components"]["mock"] == 100  # the percent cannot pass 100


@pytest.mark.django_db
def test_two_mocks_never_show_two_of_one(api, ids, enrolled):
    """The reported bug: 'Mock tests 2 of 1 tests, 100%'."""
    log(api, ids, "mock_done", value="40")
    log(api, ids, "mock_done", value="45")
    row = chapter(api, ids)
    assert row["mock_count"] == 1 and row["activities"]["mocks"]["done"] <= row["targets"]["mocks"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(connection.vendor != "postgresql", reason="row locks only serialise on PostgreSQL (CI runs it)")
def test_two_parallel_logs_for_the_last_slot_create_exactly_one_event(api, ids, enrolled):
    user_id = Enrollment.objects.get().user_id
    outcomes: list[str] = []
    barrier = threading.Barrier(2)

    def attempt():
        try:
            barrier.wait()
            services.record_event_result(user_id, ids["gst"], "mock_done", None, "manual", uuid.uuid4())
            outcomes.append("created")
        except Exception as exc:  # noqa: BLE001
            outcomes.append(type(exc).__name__)
        finally:
            connection.close()

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(outcomes) == ["TargetReachedError", "created"]
    assert CoverageEvent.objects.filter(type="mock_done").count() == 1


# --- the confidence gate ---------------------------------------------------------------------


@pytest.mark.django_db
def test_confidence_is_locked_below_50_percent(api, ids, enrolled):
    res = api.put(f"/coverage/chapters/{ids['gst']}/confidence/", {"confidence": "green"})
    assert res.status_code == 409
    error = res.json_body["error"]
    assert error["code"] == "confidence_locked" and error["details"] == {"required": 50, "current": 0}
    assert chapter(api, ids)["confidence"] is None
    assert chapter(api, ids)["confidence_gate"] == {"unlocked": False, "required_pct": 50, "current_pct": 0}


@pytest.mark.django_db
def test_confidence_unlocks_at_exactly_50_percent(api, ids, enrolled):
    chapter_id = ids["residential"]  # no topics: read is the whole chapter
    api.put(f"/coverage/chapters/{chapter_id}/read/", {"done": True})  # 40%
    assert api.put(f"/coverage/chapters/{chapter_id}/confidence/", {"confidence": "red"}).status_code == 409
    api.post("/coverage/events/", {"chapter_id": chapter_id, "type": "revision_done"})  # 40 + 10 = 50%
    res = api.put(f"/coverage/chapters/{chapter_id}/confidence/", {"confidence": "red"})
    assert res.status_code == 200 and res.json_body["chapter"]["coverage_pct"] == 50
    assert res.json_body["chapter"]["confidence_gate"]["unlocked"] is True


@pytest.mark.django_db
def test_clearing_confidence_is_always_allowed_and_an_earlier_rating_stays_when_the_percent_drops(api, ids, enrolled):
    for t in ids["topics"]:
        api.put(f"/coverage/topics/{t}/", {"done": True})
    log(api, ids, "practice_done")  # 40 + 15 = 55%
    assert api.put(f"/coverage/chapters/{ids['gst']}/confidence/", {"confidence": "green"}).status_code == 200
    api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": False})  # 30 + 15 = 45%: below the gate again
    row = chapter(api, ids)
    assert row["coverage_pct"] == 45 and row["confidence"] == "green"  # the rating is kept
    assert api.put(f"/coverage/chapters/{ids['gst']}/confidence/", {"confidence": "amber"}).status_code == 409
    cleared = api.put(f"/coverage/chapters/{ids['gst']}/confidence/", {"confidence": None})
    assert cleared.status_code == 200 and cleared.json_body["chapter"]["confidence"] is None


# --- honest progress wording -----------------------------------------------------------------


@pytest.mark.django_db
def test_started_chapters_explain_an_average_above_zero_with_no_chapter_done(api, ids, enrolled):
    """The '25% with 0 of 119 chapters done' report: reading alone is worth 40% of a chapter, never 100%."""
    for t in ids["topics"]:
        api.put(f"/coverage/topics/{t}/", {"done": True})
    api.put(f"/coverage/chapters/{ids['residential']}/read/", {"done": True})
    level = api.get("/coverage/overview/").json_body["level"]
    assert level["pct_simple"] > 0 and level["chapters_done"] == 0
    assert level["chapters_started"] == 2 and level["chapters_total"] == 4
    subject = next(s for s in api.get("/coverage/overview/").json_body["subjects"] if s["key"] == "taxation")
    assert subject["chapters_started"] == 2


@pytest.mark.django_db
def test_excluded_chapters_are_not_counted_as_started(api, ids, enrolled):
    api.put(f"/coverage/chapters/{ids['residential']}/read/", {"done": True})
    api.put(f"/coverage/chapters/{ids['residential']}/exclusion/", {"excluded": True})
    assert api.get("/coverage/overview/").json_body["level"]["chapters_started"] == 0


@pytest.mark.django_db
def test_the_migration_backfill_fills_started_counts_for_existing_rollups(api, ids, enrolled):
    import importlib

    from django.apps import apps

    from modules.coverage.models import Rollup

    api.put(f"/coverage/chapters/{ids['residential']}/read/", {"done": True})
    api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True})
    expected = {(r.node_type, r.node_id): r.chapters_started for r in Rollup.objects.all()}
    assert max(expected.values()) == 2
    Rollup.objects.update(chapters_started=0)  # what rows look like right after the column is added
    importlib.import_module("modules.coverage.migrations.0003_rollup_chapters_started").backfill_started(apps, None)
    assert {(r.node_type, r.node_id): r.chapters_started for r in Rollup.objects.all()} == expected
