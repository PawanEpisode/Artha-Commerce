"""FR-16 corrections: editing, deleting, merging, splitting or restoring a session keeps chapter study time exact."""

import pytest

from modules.coverage.models import ChapterProgress, CoverageEvent
from modules.syllabus.models import ExamTerm
from modules.tracking.models import StudySession

from .conftest import USER, iso, ist, manual


@pytest.fixture
def enrolled(api, scheme):
    term = ExamTerm.objects.get(level__course__code="ca", level__code="intermediate", code="2027-05")
    res = api.post("/coverage/enrollments/", {"scheme": str(scheme.id), "target_term": str(term.id)})
    assert res.status_code == 201, res.json_body


def seconds(chapter_id) -> int:
    row = ChapterProgress.objects.filter(user_id=USER, chapter_id=chapter_id).first()
    return row.total_study_seconds if row else 0


def test_shortening_a_session_takes_the_difference_back(api, ids, enrolled):
    sid = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    assert seconds(ids["gst"]) == 3600
    api.patch(f"/tracking/sessions/{sid}/", {"ended_at": iso(ist(4, 9, 45))})
    assert seconds(ids["gst"]) == 2700
    corrections = CoverageEvent.objects.filter(user_id=USER, type="study_time", value__lt=0)
    assert [int(e.value) for e in corrections] == [-900] and corrections[0].payload == {"correction": True}


def test_moving_a_session_to_another_chapter_moves_its_time(api, ids, enrolled):
    sid = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    api.patch(f"/tracking/sessions/{sid}/", {"chapter_id": ids["residential"]})
    assert (seconds(ids["gst"]), seconds(ids["residential"])) == (0, 3600)


def test_removing_the_chapter_takes_the_time_back(api, ids, enrolled):
    sid = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    api.patch(f"/tracking/sessions/{sid}/", {"chapter_id": None})
    assert seconds(ids["gst"]) == 0


def test_editing_only_the_note_adds_no_events(api, ids, enrolled):
    sid = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    before = CoverageEvent.objects.count()
    api.patch(f"/tracking/sessions/{sid}/", {"note": "revised"})
    assert CoverageEvent.objects.count() == before


def test_delete_and_undo_round_trip(api, ids, enrolled):
    sid = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    res = api.delete(f"/tracking/sessions/{sid}/")
    assert seconds(ids["gst"]) == 0
    api.post("/tracking/sessions/undo/", {"undo_token": res.json_body["undo_token"]})
    assert seconds(ids["gst"]) == 3600


def test_merge_keeps_the_total_and_undo_restores_it(api, ids, enrolled):
    a = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    b = manual(api, ist(4, 10, 20), ist(4, 11), chapter_id=ids["gst"]).json_body["id"]
    assert seconds(ids["gst"]) == 6000
    res = api.post("/tracking/sessions/merge/", {"session_ids": [a, b]})
    assert seconds(ids["gst"]) == 6000
    api.post("/tracking/sessions/undo/", {"undo_token": res.json_body["undo_token"]})
    assert seconds(ids["gst"]) == 6000 and StudySession.objects.count() == 2


def test_split_keeps_the_total_and_undo_restores_it(api, ids, enrolled):
    sid = manual(api, ist(4, 9), ist(4, 10, 30), chapter_id=ids["gst"]).json_body["id"]
    res = api.post(f"/tracking/sessions/{sid}/split/", {"at": iso(ist(4, 9, 40))})
    assert seconds(ids["gst"]) == 5400
    api.post("/tracking/sessions/undo/", {"undo_token": res.json_body["undo_token"]})
    assert seconds(ids["gst"]) == 5400


def test_a_replay_of_the_ledger_gives_the_same_total(api, ids, enrolled):
    from modules.coverage import services as cov
    from modules.coverage.models import Enrollment

    sid = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    api.patch(f"/tracking/sessions/{sid}/", {"ended_at": iso(ist(4, 9, 30))})
    cov.rebuild_enrollment(Enrollment.objects.get(user_id=USER))
    assert seconds(ids["gst"]) == 1800


def test_without_an_enrolment_edits_still_work(api, ids):
    sid = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    assert api.patch(f"/tracking/sessions/{sid}/", {"ended_at": iso(ist(4, 9, 30))}).status_code == 200
    assert not CoverageEvent.objects.exists()
