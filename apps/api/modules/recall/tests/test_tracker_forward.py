"""R2-W3 E: a finished recall session becomes ONE opt-in `source=auto` revision session in the tracker (FR-F15-73)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from core import events
from modules.recall import subscribers
from modules.recall.services import reviews, sessions, tracker_forward
from modules.tracking import services as tracking
from modules.tracking.models import StudySession

from .w5 import ME, card, days, ev

pytestmark = pytest.mark.django_db
NOW = days(2)  # 2026-10-11 08:00 UTC, 13:30 in India
CLOSE = NOW + timedelta(minutes=30)


@pytest.fixture(autouse=True)
def _wired(monkeypatch):
    events.clear()
    subscribers.register()
    monkeypatch.setattr(tracking, "_now", lambda: CLOSE)  # the tracker's own clock, pinned beside ours
    yield
    events.clear()


@pytest.fixture
def auto_on():
    tracking.update_settings(ME, {"auto_capture_enabled": True})


def run(n=3, seconds=60, chapter_id=None, capture=None, importance=1):
    """One closed session of `n` reviews of `seconds` each, on the event bus the real close uses. Returns the session."""
    s, _ = sessions.open_session(ME, uuid.uuid4(), source="today", now=NOW)
    for i in range(n):
        c = card(ME, chapter_id=chapter_id, importance=importance)
        reviews.submit_review(
            ME, ev(c, 3, NOW + timedelta(minutes=i), session_id=s.id, duration_ms=seconds * 1000), now=NOW
        )
    with capture(execute=True):
        sessions.close_session(ME, s.id, now=CLOSE)
    return s


def mine():
    return StudySession.objects.filter(user_id=ME)


def test_a_finished_session_is_forwarded_as_one_auto_revision_session(auto_on, django_capture_on_commit_callbacks):
    s = run(capture=django_capture_on_commit_callbacks)
    row = mine().get()
    assert (row.source, row.activity_type, row.focus_seconds) == ("auto", "revision", 180)
    assert row.client_id == tracker_forward.client_id_for(s.id)
    assert row.started_at == NOW and row.chapter_id is None  # a mixed or unfiled session is untagged


def test_a_session_of_one_chapter_is_tagged_with_it(auto_on, ids, django_capture_on_commit_callbacks):
    run(chapter_id=ids["gst"], capture=django_capture_on_commit_callbacks)
    row = mine().get()
    assert str(row.chapter_id) == ids["gst"] and str(row.subject_id) == ids["taxation"]


def test_with_auto_capture_off_nothing_is_written(django_capture_on_commit_callbacks):
    run(capture=django_capture_on_commit_callbacks)
    assert not mine().exists()  # off is the default: the tracker is opt-in


def test_a_running_timer_wins(auto_on, django_capture_on_commit_callbacks):
    tracking.start_stopwatch(ME, client_id=uuid.uuid4(), at=NOW - timedelta(minutes=1))
    run(capture=django_capture_on_commit_callbacks)
    assert not mine().exists()


def test_time_that_overlaps_recorded_time_is_skipped(auto_on, django_capture_on_commit_callbacks):
    tracking.add_manual(
        ME, client_id=uuid.uuid4(), started_at=NOW - timedelta(minutes=2), ended_at=NOW + timedelta(minutes=10)
    )
    run(capture=django_capture_on_commit_callbacks)
    assert mine().count() == 1 and mine().get().source == "manual"


def test_auto_time_stops_at_four_hours_a_day(auto_on, django_capture_on_commit_callbacks):
    for n in range(8):  # eight half hours earlier the same day: the cap is reached
        start = NOW - timedelta(hours=5) + timedelta(minutes=35 * n)
        tracking.record_session(
            ME,
            source="auto",
            started_at=start,
            ended_at=start + timedelta(minutes=30),
            focus_seconds=1800,
            activity_type="reading",
            forward=False,
        )
    run(capture=django_capture_on_commit_callbacks)
    assert mine().count() == 8 and not mine().filter(activity_type="revision").exists()


def test_a_session_shorter_than_a_minute_is_not_forwarded(auto_on, django_capture_on_commit_callbacks):
    run(n=1, seconds=30, capture=django_capture_on_commit_callbacks)
    assert not mine().exists()


def test_a_session_without_a_start_or_without_time_is_skipped():
    assert (
        tracker_forward.forward_session(ME, session_id=uuid.uuid4(), started_at=None, active_seconds=300) == "skipped"
    )
    assert (
        tracker_forward.forward_session(ME, session_id=uuid.uuid4(), started_at=NOW.isoformat(), active_seconds=0)
        == "skipped"
    )


def test_a_replayed_event_or_a_second_close_adds_no_second_session(auto_on, django_capture_on_commit_callbacks):
    s = run(capture=django_capture_on_commit_callbacks)
    with django_capture_on_commit_callbacks(execute=True):
        sessions.close_session(ME, s.id, now=CLOSE)  # closed already: no event at all
    subscribers.on_session_completed_tracker(
        user_id=str(ME), session_id=str(s.id), started_at=NOW.isoformat(), active_seconds=180, by_chapter=[]
    )  # the event replayed by hand
    assert mine().count() == 1


def test_the_tracker_failing_never_fails_the_close(auto_on, monkeypatch, django_capture_on_commit_callbacks):
    from modules.recall.adapters import tracking as adapter

    monkeypatch.setattr(adapter, "add_revision_session", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    s = run(capture=django_capture_on_commit_callbacks)
    assert s.id and not mine().exists()


def test_auto_time_is_not_sent_on_to_coverage(auto_on, ids, scheme, django_capture_on_commit_callbacks):
    from modules.coverage.models import CoverageEvent, Enrollment

    Enrollment.objects.create(user_id=ME, scheme=scheme, level=scheme.level)
    run(chapter_id=ids["gst"], capture=django_capture_on_commit_callbacks)
    assert mine().count() == 1 and not CoverageEvent.objects.filter(type="study_time").exists()  # `forward=False`


@pytest.mark.parametrize(
    ("by_chapter", "expected"),
    [
        ([], None),
        ([{"chapter_id": None, "reviews": 5}], None),
        ([{"chapter_id": "a", "reviews": 5}], "a"),
        ([{"chapter_id": "a", "reviews": 5}, {"chapter_id": "b", "reviews": 5}], "a"),  # exactly half is enough
        (
            [{"chapter_id": "a", "reviews": 4}, {"chapter_id": "b", "reviews": 3}, {"chapter_id": "c", "reviews": 3}],
            None,
        ),
        ([{"chapter_id": "a", "reviews": 3}, {"chapter_id": None, "reviews": 7}], None),
    ],
)
def test_the_main_chapter_needs_half_of_the_reviews(by_chapter, expected):
    assert tracker_forward.main_chapter(by_chapter) == expected
