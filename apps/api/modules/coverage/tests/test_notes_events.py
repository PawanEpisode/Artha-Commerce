"""F-03 tells coverage how many notes a chapter has (display only). Coverage subscribes by event name, never by import."""

import uuid

import pytest

from core import events
from modules.coverage.models import ChapterProgress, CoverageEvent
from modules.coverage.services import rebuild_enrollment
from modules.coverage.tests.conftest import USER

pytestmark = pytest.mark.django_db


def _payload(ids, level, notes=3, summary=False, event_id=None):
    return {
        "user_id": USER,
        "event_id": event_id or str(uuid.uuid4()),
        "level_id": level,
        "subject_key": "taxation",
        "chapter_id": ids["gst"],
        "chapter_key": "gst-itc",
        "counts": {"notes": notes, "highlights": 0, "marks": 0, "documents": 0},
        "has_summary": summary,
        "reason": "created",
    }


def _progress(ids):
    return ChapterProgress.objects.get(user_id=USER, chapter_id=ids["gst"])


def test_a_notes_event_updates_the_display_fields_and_the_ledger(api, ids, enrolled, scheme):
    events.emit("notes_chapter_counts_changed", **_payload(ids, str(scheme.level_id), notes=3, summary=True))
    p = _progress(ids)
    assert (p.notes_count, p.has_summary) == (3, True)
    event = CoverageEvent.objects.get(user_id=USER, type="note_added")
    assert event.source == "notes" and event.value == 3 and event.payload["has_summary"] is True
    body = api.get(f"/coverage/chapters/{ids['gst']}/").json_body["chapter"]
    assert body["notes_count"] == 3 and body["has_summary"] is True


def test_notes_never_move_the_percentage_or_the_start_date(api, ids, enrolled, scheme):
    before = api.get(f"/coverage/chapters/{ids['gst']}/").json_body["chapter"]
    events.emit("notes_chapter_counts_changed", **_payload(ids, str(scheme.level_id), notes=9))
    after = api.get(f"/coverage/chapters/{ids['gst']}/").json_body["chapter"]
    assert after["coverage_pct"] == before["coverage_pct"]
    assert _progress(ids).first_started_at is None


def test_replaying_the_same_event_is_harmless(ids, enrolled, scheme):
    payload = _payload(ids, str(scheme.level_id), notes=2)
    for _ in range(3):
        events.emit("notes_chapter_counts_changed", **payload)
    assert CoverageEvent.objects.filter(user_id=USER, type="note_added").count() == 1
    assert _progress(ids).notes_count == 2


def test_the_latest_count_wins_and_a_drop_to_zero_clears_it(ids, enrolled, scheme):
    events.emit("notes_chapter_counts_changed", **_payload(ids, str(scheme.level_id), notes=5, summary=True))
    events.emit("notes_chapter_counts_changed", **_payload(ids, str(scheme.level_id), notes=0, summary=False))
    p = _progress(ids)
    assert (p.notes_count, p.has_summary) == (0, False)


def test_a_student_who_is_not_enrolled_is_ignored(ids, scheme):
    events.emit("notes_chapter_counts_changed", **_payload(ids, str(scheme.level_id)))
    assert not CoverageEvent.objects.filter(type="note_added").exists()


def test_a_rebuild_replays_note_events_in_order(ids, enrolled, scheme):
    from modules.coverage.models import Enrollment

    events.emit("notes_chapter_counts_changed", **_payload(ids, str(scheme.level_id), notes=1))
    events.emit("notes_chapter_counts_changed", **_payload(ids, str(scheme.level_id), notes=4, summary=True))
    ChapterProgress.objects.filter(user_id=USER).update(notes_count=0, has_summary=False)
    rebuild_enrollment(Enrollment.objects.get(user_id=USER))
    p = _progress(ids)
    assert (p.notes_count, p.has_summary) == (4, True)


def test_end_to_end_through_the_notes_api(api, ids, enrolled, scheme, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        res = api.post("/notes/notes/", {"client_id": str(uuid.uuid4()), "body_md": "hello", "chapter_id": ids["gst"]})
    assert res.status_code == 201
    assert _progress(ids).notes_count == 1
    with django_capture_on_commit_callbacks(execute=True):
        api.delete(f"/notes/notes/{res.json_body['id']}/")
    assert _progress(ids).notes_count == 0
