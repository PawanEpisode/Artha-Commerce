import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from modules.coverage.models import ChapterProgress, CoverageEvent, Enrollment, Rollup, TopicProgress
from modules.coverage.tests.conftest import days_from_now
from modules.syllabus.tests.helpers import make_scheme

pytestmark = pytest.mark.django_db


def level_pct(api):
    return api.get("/coverage/overview/").json_body["level"]


def chapter(api, chapter_id):
    return api.get(f"/coverage/chapters/{chapter_id}/").json_body["chapter"]


# --- auth and scoping ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/coverage/overview/"),
        ("get", "/coverage/enrollments/"),
        ("get", "/coverage/due/"),
        ("get", "/coverage/settings/"),
        ("delete", "/coverage/"),
    ],
)
def test_every_coverage_endpoint_requires_auth(method, path):
    res = getattr(Client(), method)(f"/api/v1{path}")
    assert res.status_code == 401
    assert res.json()["error"]["code"] in {"not_authenticated", "authentication_failed"}


def test_another_students_data_is_never_visible(api, other_api, ids, enrolled):
    api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True})
    assert other_api.get("/coverage/overview/").status_code == 404
    assert other_api.get(f"/coverage/chapters/{ids['gst']}/").status_code == 404
    assert other_api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True}).status_code == 404
    assert other_api.patch(f"/coverage/enrollments/{enrolled['id']}/", {"archive": True}).status_code == 404
    assert other_api.get("/coverage/enrollments/").json_body["results"] == []
    other_api.post("/coverage/enrollments/", {"scheme": ids["scheme"]})
    assert level_pct(other_api)["pct_simple"] == 0  # the other student's own ticks do not leak in
    assert level_pct(api)["pct_simple"] > 0


# --- enrolment -------------------------------------------------------------------------------


def test_overview_requires_an_enrolment(api, scheme):
    res = api.get("/coverage/overview/")
    assert res.status_code == 404 and res.json_body["error"]["code"] == "not_found"


def test_enrol_creates_a_zero_percent_map(api, ids, enrolled):
    assert enrolled["scheme"]["code"] == "2023" and enrolled["target_term"]["code"] == "2027-05"
    assert ChapterProgress.objects.filter(enrollment_id=enrolled["id"]).count() == 4
    body = api.get("/coverage/overview/").json_body
    assert body["level"] == {
        "pct_simple": 0,
        "pct_weighted": 0,
        "chapters_total": 4,
        "chapters_done": 0,
        "chapters_started": 0,
    }
    assert [g["key"] for g in body["groups"]] == ["group-1", "group-2"]
    assert [s["key"] for s in body["subjects"]] == ["taxation", "corporate-laws"]
    assert body["subjects"][0]["chapters_total"] == 3 and body["due_count"] == 0


def test_one_active_enrolment_per_level(api, ids, enrolled):
    res = api.post("/coverage/enrollments/", {"scheme": ids["scheme"]})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "conflict"


def test_cannot_enrol_in_a_draft_or_unknown_scheme(api, ids):
    draft = make_scheme(publish=False, code="2025")
    assert api.post("/coverage/enrollments/", {"scheme": str(draft.id)}).status_code == 404
    assert api.post("/coverage/enrollments/", {"scheme": str(uuid.uuid4())}).status_code == 404


def test_term_must_belong_to_the_level(api, ids):
    for key in ("cs_term", "foundation_term"):  # another course, and another level of the same course
        res = api.post("/coverage/enrollments/", {"scheme": ids["scheme"], "target_term": ids[key]})
        assert res.status_code == 400 and "target_term" in res.json_body["error"]["details"]


def test_patch_enrolment_changes_date_and_archives(api, ids, enrolled):
    res = api.patch(f"/coverage/enrollments/{enrolled['id']}/", {"exam_date": days_from_now(30), "daily_hours": "4.5"})
    assert (
        res.status_code == 200 and res.json_body["days_remaining"] in (29, 30) and res.json_body["daily_hours"] == 4.5
    )
    res = api.patch(f"/coverage/enrollments/{enrolled['id']}/", {"archive": True})
    assert res.json_body["status"] == "archived"
    assert api.get("/coverage/overview/").status_code == 404
    again = api.post("/coverage/enrollments/", {"scheme": ids["scheme"]})
    assert again.status_code == 201 and again.json_body["id"] == enrolled["id"]  # enrolling again restores it


# --- topics and percentages ------------------------------------------------------------------


def test_tick_updates_chapter_subject_and_level(api, ids, enrolled):
    res = api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True})
    assert res.status_code == 200
    body = res.json_body
    assert body["chapter"]["topics_total"] == 4 and body["chapter"]["topics_done"] == 1
    assert body["chapter"]["components"]["read"] == 25 and body["chapter"]["coverage_pct"] == 10
    assert body["chapter"]["status"] == "reading"
    # taxation: chapters at 10, 0, 0 with marks weights 15, 5, 1
    assert body["subject"]["pct_simple"] == 3 and body["subject"]["pct_weighted"] == 7
    # level adds corporate laws (weight 10): 10/4 -> 3 and 150/31 -> 5
    assert body["level"]["pct_simple"] == 3 and body["level"]["pct_weighted"] == 5


def test_untick_recomputes_and_ledger_keeps_both_events(api, ids, enrolled):
    api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True})
    res = api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": False})
    assert res.json_body["chapter"]["coverage_pct"] == 0
    assert res.json_body["chapter"]["status"] == "reading"  # something happened, so not "not started"
    assert list(CoverageEvent.objects.order_by("created_at").values_list("type", flat=True)) == [
        "topic_done",
        "topic_undone",
    ]


def test_duplicate_client_id_changes_nothing(api, ids, enrolled):
    cid = str(uuid.uuid4())
    api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True, "client_id": cid})
    again = api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": False, "client_id": cid})
    assert again.status_code == 200 and again.json_body["chapter"]["topics_done"] == 1
    assert CoverageEvent.objects.count() == 1


def test_last_write_wins_between_devices(api, ids, enrolled):
    newer = (timezone.now() - timedelta(minutes=1)).isoformat()
    older = (timezone.now() - timedelta(minutes=10)).isoformat()
    api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True, "occurred_at": newer})
    res = api.put(
        f"/coverage/topics/{ids['topics'][0]}/", {"done": False, "occurred_at": older}
    )  # late arrival of an older tick
    assert res.json_body["chapter"]["topics_done"] == 1
    assert CoverageEvent.objects.count() == 2  # both are in the ledger


def test_chapter_without_topics_is_ticked_as_a_whole(api, ids, enrolled):
    res = api.put(f"/coverage/chapters/{ids['residential']}/read/", {"done": True})
    assert res.status_code == 200 and res.json_body["chapter"]["components"]["read"] == 100
    assert res.json_body["chapter"]["has_topics"] is False
    res = api.put(f"/coverage/chapters/{ids['gst']}/read/", {"done": True})
    assert res.status_code == 400  # this chapter has topics


def test_ticking_a_topic_of_a_scheme_you_are_not_enrolled_in_is_404(api, ids):
    assert api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True}).status_code == 404


# --- events, revision and status -------------------------------------------------------------


def test_events_drive_status_and_revision_schedule(api, ids, enrolled):
    for t in ids["topics"]:
        api.put(f"/coverage/topics/{t}/", {"done": True})
    assert chapter(api, ids["gst"])["coverage_pct"] == 40  # read only
    assert chapter(api, ids["gst"])["status"] == "reading"

    res = api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "practice_done"})
    assert res.status_code == 201
    row = res.json_body["chapter"]
    assert row["status"] == "practised" and row["components"]["practice"] == 50  # 1 of 2 sets
    assert row["coverage_pct"] == 55  # 100*40 + 50*30 = 5500 / 100

    row = api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "revision_done"}).json_body["chapter"]
    assert row["status"] == "revised_once" and row["revision_count"] == 1
    assert row["next_revision_due"] == days_from_now(3)

    row = api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "revision_done"}).json_body["chapter"]
    assert row["status"] == "revised_twice_plus" and row["next_revision_due"] == days_from_now(7)

    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "practice_done"})
    row = api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "mock_done", "value": "72.5"}).json_body[
        "chapter"
    ]
    assert row["coverage_pct"] == 100 and row["status"] == "exam_ready"


def test_events_accept_only_client_loggable_types(api, ids, enrolled):
    for bad in ("study_time", "topic_done", "confidence_set", "nonsense"):
        res = api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": bad})
        assert res.status_code == 400, bad


def test_event_client_id_makes_retries_safe(api, ids, enrolled):
    body = {"chapter_id": ids["gst"], "type": "revision_done", "client_id": str(uuid.uuid4())}
    api.post("/coverage/events/", body)
    api.post("/coverage/events/", body)
    assert chapter(api, ids["gst"])["revision_count"] == 1


def test_future_and_ancient_client_times_fall_back_to_server_time(api, ids, enrolled):
    api.post(
        "/coverage/events/",
        {
            "chapter_id": ids["gst"],
            "type": "practice_done",
            "occurred_at": (timezone.now() + timedelta(days=3)).isoformat(),
        },
    )
    api.post(
        "/coverage/events/",
        {
            "chapter_id": ids["gst"],
            "type": "practice_done",
            "occurred_at": (timezone.now() - timedelta(days=90)).isoformat(),
        },
    )
    for e in CoverageEvent.objects.all():
        assert abs((timezone.now() - e.occurred_at).total_seconds()) < 60


def test_study_time_is_shown_but_never_changes_the_percent(api, ids, enrolled):
    from modules.coverage import services

    before = chapter(api, ids["gst"])["coverage_pct"]
    services.record_event(enrolled_user(), ids["gst"], "study_time", 1500, "tracking", uuid.uuid4())
    row = chapter(api, ids["gst"])
    assert row["total_study_seconds"] == 1500 and row["last_studied_at"] is not None
    assert row["coverage_pct"] == before


def enrolled_user():
    return Enrollment.objects.get().user_id


def test_record_event_is_idempotent_and_soft_when_not_enrolled(api, ids, enrolled):
    from modules.coverage import services

    cid = uuid.uuid4()
    user = enrolled_user()
    services.record_event(user, ids["gst"], "study_time", 600, "tracking", cid)
    services.record_event(user, ids["gst"], "study_time", 600, "tracking", cid)
    assert chapter(api, ids["gst"])["total_study_seconds"] == 600
    assert services.record_event(uuid.uuid4(), ids["gst"], "study_time", 60, "tracking", strict=False) is None
    with pytest.raises(services.NotFoundError):
        services.record_event(uuid.uuid4(), ids["gst"], "study_time", 60, "tracking")
    with pytest.raises(services.InvalidInput):
        services.record_event(user, ids["gst"], "study_time", 0, "tracking")


# --- catch-up --------------------------------------------------------------------------------


def test_quick_catchup_marks_chapters_read_and_moves_the_ring(api, ids, enrolled):
    res = api.post("/coverage/catchup/", {"chapter_ids": [ids["gst"], ids["residential"]]})
    assert res.status_code == 200 and res.json_body["updated"] == 2
    assert chapter(api, ids["gst"])["components"]["read"] == 100
    assert chapter(api, ids["residential"])["components"]["read"] == 100
    assert res.json_body["overview"]["level"]["pct_simple"] == 20  # two chapters at 40 of four
    assert CoverageEvent.objects.filter(source="catchup").count() == 2


def test_catchup_can_also_count_a_first_revision_and_is_idempotent(api, ids, enrolled):
    cid = str(uuid.uuid4())
    body = {"chapter_ids": [ids["gst"]], "also_revised": True, "client_id": cid}
    api.post("/coverage/catchup/", body)
    again = api.post("/coverage/catchup/", body)
    assert again.json_body["duplicate"] is True
    row = chapter(api, ids["gst"])
    assert row["revision_count"] == 1 and row["status"] == "revised_once"
    assert TopicProgress.objects.filter(is_done=True).count() == 4


def test_catchup_rejects_foreign_chapters(api, ids, enrolled):
    res = api.post("/coverage/catchup/", {"chapter_ids": [str(uuid.uuid4())]})
    assert res.status_code == 400


# --- exclusion, confidence, due list ---------------------------------------------------------


def test_excluding_a_chapter_removes_it_from_the_maths_and_restores_on_include(api, ids, enrolled):
    api.post("/coverage/catchup/", {"chapter_ids": [ids["gst"]]})
    before = api.get("/coverage/overview/").json_body["subjects"][0]
    assert before["chapters_total"] == 3
    res = api.put(f"/coverage/chapters/{ids['heads']}/exclusion/", {"excluded": True})
    assert res.json_body["subject"]["chapters_total"] == 2
    assert res.json_body["subject"]["pct_simple"] > before["pct_simple"]  # the denominator shrank
    res = api.put(f"/coverage/chapters/{ids['gst']}/exclusion/", {"excluded": True})
    assert chapter(api, ids["gst"])["coverage_pct"] == 40  # progress is kept, just not counted
    res = api.put(f"/coverage/chapters/{ids['gst']}/exclusion/", {"excluded": False})
    assert res.json_body["subject"]["chapters_total"] == 2
    api.put(f"/coverage/chapters/{ids['heads']}/exclusion/", {"excluded": False})
    assert api.get("/coverage/overview/").json_body["subjects"][0]["pct_simple"] == before["pct_simple"]


def test_excluding_a_whole_subject(api, ids, enrolled):
    res = api.put(f"/coverage/subjects/{ids['laws']}/exclusion/", {"excluded": True})
    assert res.json_body["changed"] == 1
    overview = res.json_body["overview"]
    assert overview["level"]["chapters_total"] == 3
    assert next(s for s in overview["subjects"] if s["key"] == "corporate-laws")["excluded_chapters"] == 1


def test_confidence_rating_is_stored_per_chapter(api, ids, enrolled):
    for t in ids["topics"][:3]:  # 30% read: still locked
        api.put(f"/coverage/topics/{t}/", {"done": True})
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "practice_done"})  # 30 + 15 = 45%: locked
    assert chapter(api, ids["gst"])["coverage_pct"] == 45
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "practice_done"})  # 30 + 30 = 60%
    res = api.put(f"/coverage/chapters/{ids['gst']}/confidence/", {"confidence": "amber"})
    assert res.json_body["chapter"]["confidence"] == "amber"
    assert api.put(f"/coverage/chapters/{ids['gst']}/confidence/", {"confidence": "purple"}).status_code == 400
    assert (
        api.put(f"/coverage/chapters/{ids['gst']}/confidence/", {"confidence": None}).json_body["chapter"]["confidence"]
        is None
    )


def test_due_list_orders_overdue_first_then_heavier_chapters(api, ids, enrolled):
    api.post("/coverage/events/", {"chapter_id": ids["residential"], "type": "revision_done"})  # weight 5
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "revision_done"})  # weight 15
    assert api.get("/coverage/due/").json_body["results"] == []
    assert api.get("/coverage/overview/").json_body["due_count"] == 0
    rows = api.get(f"/coverage/due/?today={days_from_now(3)}").json_body["results"]
    assert [r["id"] for r in rows] == [ids["gst"], ids["residential"]]  # same overdue days, heavier first
    assert rows[0]["overdue_days"] == 0 and rows[0]["subject"]["key"] == "taxation"
    rows = api.get(f"/coverage/due/?today={days_from_now(10)}").json_body["results"]
    assert rows[0]["overdue_days"] == 7


def test_chapter_detail_shows_topics_events_and_revision_history(api, ids, enrolled):
    api.put(f"/coverage/topics/{ids['topics'][1]}/", {"done": True})
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "revision_done"})
    body = api.get(f"/coverage/chapters/{ids['gst']}/").json_body
    assert [t["is_done"] for t in body["topics"]] == [False, True, False, False]
    assert body["subject"]["key"] == "taxation"
    assert len(body["events"]) == 2 and len(body["revision_history"]) == 1


def test_subject_coverage_lists_chapters_in_order(api, ids, enrolled):
    body = api.get(f"/coverage/subjects/{ids['taxation']}/").json_body
    assert [c["key"] for c in body["chapters"]] == ["gst-itc", "residential-status", "heads-of-income"]
    assert body["subject"]["chapters_total"] == 3
    assert api.get(f"/coverage/subjects/{uuid.uuid4()}/").status_code == 404


# --- settings --------------------------------------------------------------------------------


def test_settings_default_validate_and_recompute(api, ids, enrolled):
    body = api.get("/coverage/settings/").json_body
    assert {
        k: body[k] for k in ("w_read", "w_practice", "w_revise", "w_mock", "revision_days", "weighted_default")
    } == {
        "w_read": 40,
        "w_practice": 30,
        "w_revise": 20,
        "w_mock": 10,
        "revision_days": [3, 7, 21, 45],
        "weighted_default": False,
    }
    api.post("/coverage/catchup/", {"chapter_ids": [ids["gst"]]})
    assert chapter(api, ids["gst"])["coverage_pct"] == 40

    bad = api.put(
        "/coverage/settings/", {"w_read": 50, "w_practice": 30, "w_revise": 20, "w_mock": 10, "revision_days": [3]}
    )
    assert bad.status_code == 400 and "weights" in bad.json_body["error"]["details"]
    bad = api.put(
        "/coverage/settings/", {"w_read": 40, "w_practice": 30, "w_revise": 20, "w_mock": 10, "revision_days": []}
    )
    assert bad.status_code == 400

    ok = api.put(
        "/coverage/settings/",
        {
            "w_read": 70,
            "w_practice": 10,
            "w_revise": 10,
            "w_mock": 10,
            "revision_days": [2, 5],
            "weighted_default": True,
        },
    )
    assert ok.status_code == 200 and ok.json_body["weighted_default"] is True
    assert chapter(api, ids["gst"])["coverage_pct"] == 70  # recomputed at once
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "revision_done"})
    assert chapter(api, ids["gst"])["next_revision_due"] == days_from_now(2)

    reset = api.delete("/coverage/settings/")
    assert reset.json_body["w_read"] == 40 and reset.json_body["revision_days"] == [3, 7, 21, 45]
    assert chapter(api, ids["gst"])["coverage_pct"] > 40  # one revision now also counts


# --- export and delete -----------------------------------------------------------------------


def test_export_and_delete_all(api, other_api, ids, enrolled):
    api.put(f"/coverage/topics/{ids['topics'][0]}/", {"done": True})
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "revision_done"})
    other_api.post("/coverage/enrollments/", {"scheme": ids["scheme"]})
    data = api.get("/coverage/export/").json_body
    assert len(data["enrollments"]) == 1 and len(data["events"]) == 2 and len(data["chapter_progress"]) == 4
    assert data["settings"]["w_read"] == 40 and data["topic_progress"][0]["is_done"] is True

    assert api.delete("/coverage/").status_code == 204
    assert api.get("/coverage/export/").json_body["enrollments"] == []
    assert not CoverageEvent.objects.filter(user_id=enrolled_user_for("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")).exists()
    assert Enrollment.objects.count() == 1  # the other student is untouched
    assert Rollup.objects.count() > 0


def enrolled_user_for(sub):
    return sub


def test_chapter_page_links_to_neighbouring_chapters(api, ids, enrolled):
    body = api.get(f"/coverage/chapters/{ids['residential']}/").json_body
    assert body["prev_chapter"]["id"] == ids["gst"]
    assert body["next_chapter"]["id"] == ids["heads"]
    assert api.get(f"/coverage/chapters/{ids['gst']}/").json_body["prev_chapter"] is None
