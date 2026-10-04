import random
import uuid
from copy import deepcopy

import pytest
from django.core.management import call_command

from modules.coverage import services
from modules.coverage.models import ChapterProgress, CoverageEvent, Enrollment, Rollup, TopicProgress
from modules.syllabus.models import Chapter
from modules.syllabus.services import build_default_chapter_map, publish_scheme
from modules.syllabus.tests.helpers import SPEC, make_scheme

pytestmark = pytest.mark.django_db

DERIVED = [
    "status",
    "confidence",
    "is_excluded",
    "implicit_topic_done",
    "read_pct",
    "practice_pct",
    "revise_pct",
    "mock_pct",
    "coverage_pct",
    "practice_count",
    "mock_count",
    "revision_count",
    "total_study_seconds",
    "first_started_at",
    "last_studied_at",
    "last_revised_at",
    "next_revision_due",
]


def snapshot(enrollment):
    chapters = {
        str(p.chapter_id): {f: getattr(p, f) for f in DERIVED}
        for p in ChapterProgress.objects.filter(enrollment=enrollment)
    }
    topics = {str(t.topic_id): t.is_done for t in TopicProgress.objects.filter(enrollment=enrollment)}
    rollups = {
        (r.node_type, str(r.node_id)): (r.pct_simple, r.pct_weighted, r.chapters_total, r.chapters_done)
        for r in Rollup.objects.filter(enrollment=enrollment)
    }
    return chapters, topics, rollups


def done_topics(snap):
    return {k for k, v in snap[1].items() if v}


def test_rebuilding_from_the_ledger_gives_the_same_result_as_the_live_path(api, ids, enrolled):
    rng = random.Random(7)
    chapter_ids = [ids["gst"], ids["residential"], ids["heads"], ids["companies"]]
    for _ in range(60):
        action = rng.choice(["tick", "tick", "event", "event", "catchup", "exclude", "confidence", "implicit", "time"])
        if action == "tick":
            api.put(
                f"/coverage/topics/{rng.choice(ids['topics'])}/",
                {"done": rng.random() < 0.7, "client_id": str(uuid.uuid4())},
            )
        elif action == "event":
            api.post(
                "/coverage/events/",
                {
                    "chapter_id": rng.choice(chapter_ids),
                    "type": rng.choice(["practice_done", "mock_done", "revision_done"]),
                },
            )
        elif action == "catchup":
            api.post(
                "/coverage/catchup/", {"chapter_ids": rng.sample(chapter_ids, 2), "also_revised": rng.random() < 0.3}
            )
        elif action == "exclude":
            api.put(f"/coverage/chapters/{rng.choice(chapter_ids)}/exclusion/", {"excluded": rng.random() < 0.5})
        elif action == "confidence":
            api.put(
                f"/coverage/chapters/{rng.choice(chapter_ids)}/confidence/",
                {"confidence": rng.choice(["red", "amber", "green", None])},
            )
        elif action == "implicit":
            api.put(f"/coverage/chapters/{ids['residential']}/read/", {"done": rng.random() < 0.6})
        else:
            services.record_event(
                Enrollment.objects.get().user_id,
                rng.choice(chapter_ids),
                "study_time",
                rng.randint(60, 3000),
                "tracking",
            )
    enrollment = Enrollment.objects.get()
    live = snapshot(enrollment)
    assert CoverageEvent.objects.count() > 40

    call_command("rebuild_coverage")
    rebuilt = snapshot(Enrollment.objects.get())
    chapters_live, topics_live, rollups_live = live
    chapters_new, topics_new, rollups_new = rebuilt
    # Topic rows that never existed live may appear as untouched on neither side; compare the done set.
    assert done_topics(live) == done_topics(rebuilt)
    for cid, fields in chapters_live.items():
        for name, value in fields.items():
            # `next_revision_due` and last timestamps come from event times, which the rebuild reads back from the ledger.
            assert chapters_new[cid][name] == value, (cid, name)
    assert rollups_new == rollups_live


def test_rebuild_after_changing_weights_matches_recompute(api, ids, enrolled):
    api.post("/coverage/catchup/", {"chapter_ids": [ids["gst"]], "also_revised": True})
    api.put(
        "/coverage/settings/",
        {
            "w_read": 25,
            "w_practice": 25,
            "w_revise": 25,
            "w_mock": 25,
            "revision_days": [3, 7, 21, 45],
            "weighted_default": False,
        },
    )
    live = snapshot(Enrollment.objects.get())
    services.rebuild_enrollment(Enrollment.objects.get())
    assert snapshot(Enrollment.objects.get())[0] == live[0]


# --- scheme switch ---------------------------------------------------------------------------


def second_scheme():
    spec = deepcopy(SPEC)
    spec["subjects"][0]["chapters"].append({"key": "new-chapter", "name": "Brand new chapter"})
    spec["subjects"][0]["chapters"] = [c for c in spec["subjects"][0]["chapters"] if c["key"] != "heads-of-income"]
    # the new scheme starts after the old one ends
    spec["scheme"]["from_term"] = "2027-11"
    new = make_scheme(publish=False, code="2025", spec=spec, from_term="2027-11")
    return new


def test_switching_scheme_carries_progress_and_lists_what_is_new_or_removed(api, ids, enrolled):
    from modules.syllabus.models import Scheme

    old = Scheme.objects.get(code="2023")
    old.to_term = old.level.course.terms.get(code="2027-05")
    old.save()
    new = second_scheme()
    publish_scheme(new)
    assert build_default_chapter_map(old, new) == 3  # gst-itc, residential-status, companies-act

    for t in ids["topics"][:3]:
        api.put(f"/coverage/topics/{t}/", {"done": True})
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "practice_done"})
    api.post("/coverage/events/", {"chapter_id": ids["gst"], "type": "revision_done"})
    api.put(f"/coverage/chapters/{ids['gst']}/confidence/", {"confidence": "green"})
    api.put(f"/coverage/chapters/{ids['residential']}/read/", {"done": True})
    before = api.get(f"/coverage/chapters/{ids['gst']}/").json_body["chapter"]
    old_enrollment = Enrollment.objects.get()
    old_level = api.get("/coverage/overview/").json_body["level"]

    res = api.patch(f"/coverage/enrollments/{old_enrollment.id}/", {"scheme": str(new.id)})
    assert res.status_code == 200, res.json_body
    assert res.json_body["scheme"]["code"] == "2025" and res.json_body["carried_from"] == str(old_enrollment.id)
    assert res.json_body["switch_summary"] == {"carried_chapters": 3, "new_chapters": 1, "removed_chapters": 1}

    old_enrollment.refresh_from_db()
    assert old_enrollment.status == "archived"
    overview = api.get("/coverage/overview/").json_body
    assert overview["enrollment"]["scheme"]["code"] == "2025"
    assert overview["level"]["chapters_total"] == 4  # gst, residential, new chapter, companies

    # the same chapter keeps its percent in the new scheme (FR-28)
    new_gst = Chapter.objects.get(subject__scheme=new, key="gst-itc")
    after = api.get(f"/coverage/chapters/{new_gst.id}/").json_body
    assert after["chapter"]["coverage_pct"] == before["coverage_pct"]
    assert after["chapter"]["revision_count"] == 1 and after["chapter"]["confidence"] == "green"
    assert [t["is_done"] for t in after["topics"]] == [True, True, True, False]
    new_chapter = Chapter.objects.get(key="new-chapter")
    assert api.get(f"/coverage/chapters/{new_chapter.id}/").json_body["chapter"]["coverage_pct"] == 0
    assert old_level["chapters_total"] == 4

    # carry-over events are in the ledger, and a rebuild reproduces the same state
    assert CoverageEvent.objects.filter(source="carryover").exists()
    live = snapshot(Enrollment.objects.get(status="active"))
    services.rebuild_enrollment(Enrollment.objects.get(status="active"))
    assert snapshot(Enrollment.objects.get(status="active")) == live


def test_switch_validations(api, ids, enrolled):
    enrollment = Enrollment.objects.get()
    assert (
        api.patch(f"/coverage/enrollments/{enrollment.id}/", {"scheme": ids["scheme"]}).status_code == 400
    )  # same scheme
    draft = make_scheme(publish=False, code="2030")
    assert api.patch(f"/coverage/enrollments/{enrollment.id}/", {"scheme": str(draft.id)}).status_code == 404
