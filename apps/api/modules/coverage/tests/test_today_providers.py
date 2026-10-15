"""What coverage offers Today: revisions due, the next topic, the next chapter (F-13 W2)."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from modules.coverage import selectors, services, today_providers
from modules.coverage.models import ChapterProgress, CoverageEvent, Enrollment
from modules.syllabus.models import Subject
from modules.today import registry
from modules.today.domain import deeplinks
from modules.today.registry import (
    EnrollmentCtx,
    PaperCtx,
    PlanContext,
    TaskRequest,
    TaskView,
)

from .conftest import USER

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _registered():
    """Another module's tests may empty the registry; the coverage providers are registered by the app at start-up."""
    registry.clear()
    today_providers.register()


TODAY = date(2026, 10, 14)


def request(user_id=USER, papers=None, limit=20, days_to_exam=60):
    enrollment = Enrollment.objects.get(user_id=user_id, status="active")
    subjects = papers or list(Subject.objects.filter(scheme=enrollment.scheme))
    ctx = PlanContext(
        user_id=uuid.UUID(user_id),
        local_date=TODAY,
        tz="Asia/Kolkata",
        enrollment=EnrollmentCtx(
            id=enrollment.id,
            scheme_id=enrollment.scheme_id,
            course_code="ca",
            level_code="intermediate",
            exam_date=None,
            term_code=None,
            daily_hours=None,
        ),
        days_to_exam=days_to_exam,
        phase="build",
        papers=tuple(PaperCtx(s.id, s.key, s.name, s.paper_number, s.kind, 0, None) for s in subjects),
        done_keys=frozenset(),
        suppressed_keys=frozenset(),
        budget_minutes=60,
        comeback=False,
        seed=1,
        is_preview=False,
    )
    return TaskRequest(ctx=ctx, limit=limit, deadline_ms=400)


def due(chapter_key, on, count=1):
    ChapterProgress.objects.filter(user_id=USER, chapter__key=chapter_key).update(
        next_revision_due=on, revision_count=count
    )


def test_both_providers_are_registered_by_the_app():
    assert registry.get_provider("coverage.revision") is not None
    assert {k.name for p in registry.providers() if p.name.startswith("coverage.") for k in p.kinds} >= {
        "revise_chapter",
        "next_topic",
        "next_chapter",
    }
    assert registry.manual_action("coverage.log_revision") is not None


def test_a_chapter_due_for_revision_is_offered_with_why(enrolled):
    due("gst-itc", TODAY - timedelta(days=3), count=1)
    result = today_providers.revision_candidates(request())
    [c] = result.candidates
    assert c.kind == "revise_chapter" and c.reason_code == "revision_overdue"
    assert c.reason == "Revision 2 was due 3 days ago"
    assert c.dedupe_key.startswith("revise:") and c.dedupe_key.endswith(":2")
    assert c.manual_action.key == "coverage.log_revision"
    assert deeplinks.valid_link(c.link.path, c.link.search)
    assert 0 <= c.signals.urgency <= 100 and c.signals.urgency == 70
    assert result.backlog_count == 0


def test_due_today_and_future_chapters(enrolled):
    due("gst-itc", TODAY)
    due("companies-act", TODAY + timedelta(days=1))
    [c] = today_providers.revision_candidates(request()).candidates
    assert c.reason_code == "revision_due_today" and c.signals.urgency == 40


def test_a_big_backlog_becomes_a_count_not_a_wall_of_tasks(enrolled):
    for key in ("gst-itc", "residential-status", "heads-of-income", "companies-act"):
        due(key, TODAY - timedelta(days=2))
    result = today_providers.revision_candidates(request(limit=2))
    assert len(result.candidates) == 2 and result.backlog_count == 2
    assert result.backlog_link.path == "/app/revision"


def test_most_overdue_comes_first_and_the_order_is_stable(enrolled):
    due("gst-itc", TODAY - timedelta(days=1))
    due("companies-act", TODAY - timedelta(days=9))
    first = today_providers.revision_candidates(request()).candidates
    again = today_providers.revision_candidates(request()).candidates
    assert [c.dedupe_key for c in first] == [c.dedupe_key for c in again]
    assert "Companies" in first[0].title or first[0].signals.urgency > first[1].signals.urgency


def test_only_papers_in_the_context_are_offered(enrolled, ids):
    due("gst-itc", TODAY - timedelta(days=1))
    laws = [Subject.objects.get(key="corporate-laws")]
    assert not today_providers.revision_candidates(request(papers=laws)).candidates


def test_excluded_chapters_are_not_offered(enrolled, api, ids):
    due("gst-itc", TODAY - timedelta(days=1))
    services.set_exclusion(USER, ids["gst"], True)
    assert not today_providers.revision_candidates(request()).candidates


def test_no_enrolment_offers_nothing(db):
    ctx = PlanContext(
        user_id=uuid.UUID(USER),
        local_date=TODAY,
        tz="UTC",
        enrollment=None,
        days_to_exam=None,
        phase="steady",
        papers=(),
        done_keys=frozenset(),
        suppressed_keys=frozenset(),
        budget_minutes=60,
        comeback=False,
        seed=1,
        is_preview=False,
    )
    req = TaskRequest(ctx=ctx, limit=10, deadline_ms=400)
    assert not today_providers.revision_candidates(req).candidates
    assert not today_providers.syllabus_candidates(req).candidates


def test_a_new_student_gets_one_next_chapter_per_paper(enrolled):
    got = today_providers.syllabus_candidates(request()).candidates
    assert {c.kind for c in got} == {"next_chapter"}
    assert len({c.subject_id for c in got}) == len(got) == Subject.objects.count()
    assert all(deeplinks.valid_link(c.link.path, c.link.search) for c in got)


def test_a_chapter_in_progress_offers_its_next_topic(enrolled, ids):
    services.tick_topic(USER, ids["topics"][0], done=True)
    got = {c.chapter_id: c for c in today_providers.syllabus_candidates(request()).candidates}
    c = got[uuid.UUID(ids["gst"])]
    assert c.kind == "next_topic" and c.dedupe_key == f"topic:{ids['topics'][1]}"
    assert c.reason_code == "next_in_syllabus"


def test_selector_dates_are_the_students_local_dates(enrolled, ids):
    """AUD-018: a session at 01:00 IST on the 14th is the 13th in UTC; the student's calendar says the 14th."""
    moment = datetime(2026, 10, 13, 19, 30, tzinfo=UTC)
    ChapterProgress.objects.filter(user_id=USER, chapter_id=ids["gst"]).update(last_studied_at=moment)
    enrollment = Enrollment.objects.get(user_id=USER, status="active")
    local = selectors.study_state(USER, enrollment, "Asia/Kolkata")
    utc = selectors.study_state(USER, enrollment, "UTC")
    pick = lambda st: next(c for s in st.subjects for c in s.chapters if str(c.chapter_id) == ids["gst"])  # noqa: E731
    assert pick(local).last_studied_on == date(2026, 10, 14)
    assert pick(utc).last_studied_on == date(2026, 10, 13)


def test_stored_due_date_is_derived_from_the_students_calendar_day(enrolled, ids):
    """AUD-018 fixed: 01:00 IST on the 14th is the 13th in UTC, but the revision happened on the student's 14th."""
    at = datetime(2026, 10, 13, 19, 30, tzinfo=UTC)  # 01:00 IST on the 14th
    services.record_event(USER, ids["gst"], CoverageEvent.Type.REVISION_DONE, occurred_at=at, client_id=uuid.uuid4())
    progress = ChapterProgress.objects.get(user_id=USER, chapter_id=ids["gst"])
    assert progress.next_revision_due == date(
        2026, 10, 17
    )  # the first gap counts from the 14th (the UTC day gave the 16th)


def test_a_revision_late_in_the_evening_counts_from_that_day(enrolled, ids):
    at = datetime(2026, 10, 14, 17, 30, tzinfo=UTC)  # 23:00 IST on the 14th: same day in both calendars
    services.record_event(USER, ids["gst"], CoverageEvent.Type.REVISION_DONE, occurred_at=at, client_id=uuid.uuid4())
    assert ChapterProgress.objects.get(user_id=USER, chapter_id=ids["gst"]).next_revision_due == date(2026, 10, 17)


def test_the_students_own_time_zone_is_used(enrolled, ids):
    from modules.tracking.models import TrackerSettings

    TrackerSettings.objects.update_or_create(user_id=USER, defaults={"tz": "America/Los_Angeles"})
    at = datetime(2026, 10, 14, 3, 0, tzinfo=UTC)  # 20:00 on the 13th in Los Angeles
    services.record_event(USER, ids["gst"], CoverageEvent.Type.REVISION_DONE, occurred_at=at, client_id=uuid.uuid4())
    assert ChapterProgress.objects.get(user_id=USER, chapter_id=ids["gst"]).next_revision_due == date(2026, 10, 16)


def test_a_rebuild_gives_the_same_due_date_as_the_live_path(enrolled, ids):
    at = datetime(2026, 10, 13, 19, 30, tzinfo=UTC)
    services.record_event(USER, ids["gst"], CoverageEvent.Type.REVISION_DONE, occurred_at=at, client_id=uuid.uuid4())
    live = ChapterProgress.objects.get(user_id=USER, chapter_id=ids["gst"]).next_revision_due
    services.rebuild_enrollment(Enrollment.objects.get(user_id=USER, status="active"))
    assert (
        ChapterProgress.objects.get(user_id=USER, chapter_id=ids["gst"]).next_revision_due == live == date(2026, 10, 17)
    )


def test_ticking_by_hand_logs_one_revision_even_if_replayed(enrolled, ids):
    task = TaskView(
        id=uuid.uuid4(),
        kind="revise_chapter",
        dedupe_key="revise:x:1",
        local_date=TODAY,
        state="done",
        subject_id=None,
        chapter_id=uuid.UUID(ids["gst"]),
        target_value=None,
        progress_value=0,
        payload={},
    )
    today_providers.log_revision(uuid.UUID(USER), task)
    today_providers.log_revision(uuid.UUID(USER), task)
    assert CoverageEvent.objects.filter(user_id=USER, type="revision_done", source_ref="today").count() == 1
    assert ChapterProgress.objects.get(user_id=USER, chapter_id=ids["gst"]).revision_count == 1


def test_a_chapter_less_task_logs_nothing(enrolled):
    task = TaskView(uuid.uuid4(), "revise_chapter", "k", TODAY, "done", None, None, None, 0, {})
    today_providers.log_revision(uuid.UUID(USER), task)
    assert CoverageEvent.objects.filter(type="revision_done").count() == 0
