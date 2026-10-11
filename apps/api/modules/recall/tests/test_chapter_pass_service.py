"""R2-W3 A: the chapter recall pass (FR-F15-64): the check after a session closes, the 7-day rule, the event and its coverage consumer."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest

from core import events
from core import jobs as core_jobs
from core.models import Job
from modules.coverage.models import ChapterProgress, CoverageEvent, Enrollment
from modules.recall import jobs, subscribers
from modules.recall.models import RecallSession, RecallSettings
from modules.recall.selectors import chapter_pass as reads
from modules.recall.services import chapter_pass, reviews, sessions
from modules.syllabus.models import Chapter

from .w5 import ME, card, days, ev, minutes

pytestmark = pytest.mark.django_db
NOW = days(2)


@pytest.fixture(autouse=True)
def _wired():
    """Some tests in the suite clear the event bus; wire the recall subscribers again (idempotent)."""
    events.clear()
    subscribers.register()
    jobs.register_handlers()
    yield
    events.clear()


@pytest.fixture
def chapter(scheme):
    return Chapter.objects.get(key="gst-itc")


@pytest.fixture
def enrolled(scheme):
    return Enrollment.objects.create(user_id=ME, scheme=scheme, level=scheme.level)


def make_set(chapter, n=5, importance=1, **extra):
    return [card(ME, chapter_id=chapter.id, importance=importance, **extra) for _ in range(n)]


def study(cards, rating=3, at=None, *, source="chapter", finish=True, now=NOW, **kw):
    """One session in which each card is reviewed once; closes it unless asked not to. Returns the session."""
    at = at or minutes(0)
    s, _ = sessions.open_session(ME, uuid.uuid4(), source=source, now=now)
    for i, c in enumerate(cards):
        reviews.submit_review(ME, ev(c, rating, at + timedelta(minutes=i), session_id=s.id, **kw), now=now)
    if finish:
        sessions.close_session(ME, s.id, now=now)
    return s


def announce(session, now=NOW, capture=None):
    if capture is None:
        return chapter_pass.evaluate_session(ME, session.id, now=now)
    with capture(execute=True):
        return chapter_pass.evaluate_session(ME, session.id, now=now)


def listen():
    seen = []
    events.subscribe(chapter_pass.EVENT_CHAPTER_PASS, lambda **p: seen.append(p))
    return seen


# ------------------------------------------------------------------------------------------------ the rule on real rows
def test_four_of_five_important_cards_reviewed_pass_the_chapter(chapter, django_capture_on_commit_callbacks):
    cards = make_set(chapter, 5)
    seen = listen()
    s = study(cards[:4])
    out = announce(s, capture=django_capture_on_commit_callbacks)
    assert [(a.set_size, a.coverage_of_set, a.new) for a in out] == [(5, 0.8, True)]
    assert len(seen) == 1
    payload = seen[0]
    assert (payload["chapter_id"], payload["chapter_key"], payload["set_size"], payload["coverage_of_set"]) == (
        str(chapter.id),
        "gst-itc",
        5,
        0.8,
    )
    assert payload["session_id"] == str(s.id) and payload["user_id"] == str(ME) and payload["local_date"]
    assert set(payload) == {
        "user_id",
        "session_id",
        "chapter_id",
        "chapter_key",
        "local_date",
        "set_size",
        "coverage_of_set",
    }  # ids and counts only


def test_three_of_five_is_not_a_pass_and_four_cards_can_never_pass(chapter):
    assert announce(study(make_set(chapter, 5)[:3])) == []
    other = Chapter.objects.get(key="residential-status")
    assert announce(study(make_set(other, 4))) == []  # a set of four is too small whatever was reviewed


def test_only_mandatory_and_important_cards_make_the_set(chapter):
    bullets = make_set(chapter, 5, importance=0)
    assert announce(study(bullets)) == []  # five bullets are not a set
    mixed = make_set(chapter, 3, importance=2) + make_set(chapter, 2, importance=1)
    extra_bullets = make_set(chapter, 10, importance=0)
    out = announce(study(mixed + extra_bullets))
    assert [(a.set_size, a.coverage_of_set) for a in out] == [(5, 1.0)]  # the ten bullets do not dilute it


def test_again_does_not_count_and_hard_does(chapter):
    cards = make_set(chapter, 5)
    assert announce(study(cards, rating=1)) == []
    assert [a.coverage_of_set for a in announce(study(cards, rating=2))] == [1.0]  # Hard or better


def test_paused_deleted_and_other_peoples_cards_are_not_in_the_set(chapter):
    cards = make_set(chapter, 6)
    cards[0].status = "suspended"
    cards[0].save()
    other = card(uuid.uuid4(), chapter_id=chapter.id, importance=1)
    state = reads.pass_state(ME, chapter.id, now=NOW)
    assert state.set_size == 5 and other.id not in {c.id for c in cards}


def test_an_undone_review_does_not_count(chapter):
    cards = make_set(chapter, 5)
    s = study(cards[:4], finish=False)
    first = s and next(iter(cards[:1]))
    from modules.recall.models import RecallReviewLog

    row = RecallReviewLog.objects.filter(user_id=ME, card_id=first.id, kind="review").first()
    reviews.undo_review(ME, uuid.uuid4(), row.id, now=NOW)
    sessions.close_session(ME, s.id, now=NOW)
    assert announce(s) == []  # three of five once the first is undone


def test_reviews_older_than_seven_days_have_left_the_window(chapter):
    cards = make_set(chapter, 5)
    old = NOW - timedelta(days=7)
    s = study(cards, at=old, now=old)
    assert [a.new for a in announce(s, now=old + timedelta(days=6))] == [True]  # 6 days later: still counts
    s2 = study(cards[:1], at=NOW, now=NOW)
    assert announce(s2, now=NOW) == []  # 7 days later the old reviews no longer count


# ------------------------------------------------------------------------------------------------ once per 7 days
def test_a_chapter_is_announced_once_in_seven_days_then_again(chapter, django_capture_on_commit_callbacks):
    cards = make_set(chapter, 5)
    seen = listen()
    first = study(cards, at=minutes(0))
    assert [a.new for a in announce(first, now=minutes(10), capture=django_capture_on_commit_callbacks)] == [True]
    later = study(cards, at=minutes(0) + timedelta(days=2), now=NOW + timedelta(days=2))
    assert announce(later, now=NOW + timedelta(days=2), capture=django_capture_on_commit_callbacks) == []
    assert len(seen) == 1
    just_before = study(cards, at=minutes(0) + timedelta(days=6), now=NOW + timedelta(days=6, hours=-1))
    assert announce(just_before, now=minutes(10) + timedelta(days=7) - timedelta(seconds=1)) == []
    after = study(cards, at=minutes(0) + timedelta(days=7), now=NOW + timedelta(days=7))
    assert [
        a.new for a in announce(after, now=minutes(10) + timedelta(days=7), capture=django_capture_on_commit_callbacks)
    ] == [True]
    assert len(seen) == 2


def test_the_week_boundary_does_not_decide_a_rolling_seven_days(chapter):
    """A pass on a Sunday does not allow another on the Monday (the ERD's ISO week would have)."""
    cards = make_set(chapter, 5)
    sunday = days(0)  # 2026-10-09 is a Friday; what matters is only that the two instants straddle an ISO week
    assert sunday.weekday() == 4
    first = study(cards, at=sunday, now=sunday + timedelta(hours=1))
    assert announce(first, now=sunday + timedelta(hours=1))
    next_week = sunday + timedelta(days=3, hours=2)  # Monday of the next ISO week
    assert next_week.isocalendar().week != sunday.isocalendar().week
    again = study(cards, at=next_week, now=next_week)
    assert announce(again, now=next_week) == []


def test_two_chapters_in_one_session_are_judged_separately(chapter, scheme):
    other = Chapter.objects.get(key="residential-status")
    a, b = make_set(chapter, 5), make_set(other, 5)
    out = announce(study(a + b[:2]))
    assert {x.chapter_key for x in out} == {"gst-itc"}


# ------------------------------------------------------------------------------------------------ idempotency
def test_evaluating_a_session_twice_announces_it_twice_but_writes_it_once(chapter, django_capture_on_commit_callbacks):
    cards = make_set(chapter, 5)
    seen = listen()
    s = study(cards)
    one = announce(s, capture=django_capture_on_commit_callbacks)
    two = announce(s, capture=django_capture_on_commit_callbacks)
    assert [a.new for a in one] == [True] and [a.new for a in two] == [False]
    assert len(RecallSession.objects.get(pk=s.id).chapter_passes) == 1
    assert len(seen) == 2 and seen[0] == seen[1]  # the same payload: consumers are idempotent


def test_an_open_session_is_not_evaluated(chapter):
    s = study(make_set(chapter, 5), finish=False)
    assert announce(s) == []
    assert RecallSession.objects.get(pk=s.id).chapter_passes == []


def test_a_missing_session_is_nothing(chapter):
    assert chapter_pass.evaluate_session(ME, uuid.uuid4(), now=NOW) == []


# ------------------------------------------------------------------------------------------------ closing a session queues the job
def test_the_review_path_queues_nothing_and_closing_queues_one_job(chapter, django_capture_on_commit_callbacks):
    cards = make_set(chapter, 5)
    s = study(cards, finish=False)
    assert not Job.objects.filter(type=chapter_pass.JOB_CHAPTER_PASS).exists()  # nothing on the hot path
    with django_capture_on_commit_callbacks(execute=True):
        sessions.close_session(ME, s.id, now=NOW)
        sessions.close_session(ME, s.id, now=NOW)  # a repeated close
    queued = Job.objects.filter(type=chapter_pass.JOB_CHAPTER_PASS)
    assert queued.count() == 1
    assert queued.first().payload == {"user_id": str(ME), "session_id": str(s.id)}  # ids only


def test_a_session_without_a_chapter_queues_nothing(django_capture_on_commit_callbacks):
    s = study([card(ME) for _ in range(3)], finish=False)
    with django_capture_on_commit_callbacks(execute=True):
        sessions.close_session(ME, s.id, now=NOW)
    assert not Job.objects.filter(type=chapter_pass.JOB_CHAPTER_PASS).exists()


def test_the_queued_job_runs_through_the_tick_and_announces(chapter, enrolled, django_capture_on_commit_callbacks):
    cards = make_set(chapter, 5)
    s = study(cards, finish=False)
    with django_capture_on_commit_callbacks(execute=True):
        sessions.close_session(ME, s.id, now=NOW)
    with django_capture_on_commit_callbacks(execute=True):
        ran = core_jobs.run_pending(types=jobs.LIGHT_TYPES, budget_seconds=5, worker="test")
    assert ran == 1
    assert len(RecallSession.objects.get(pk=s.id).chapter_passes) == 1
    assert ChapterProgress.objects.get(user_id=ME, chapter_id=chapter.id).revision_count == 1


# ------------------------------------------------------------------------------------------------ the coverage consumer
def revisions(chapter):
    return (
        ChapterProgress.objects.filter(user_id=ME, chapter_id=chapter.id)
        .values_list("revision_count", flat=True)
        .first()
        or 0
    )


def test_a_pass_counts_as_one_revision_in_coverage(chapter, enrolled, django_capture_on_commit_callbacks):
    s = study(make_set(chapter, 5))
    announce(s, capture=django_capture_on_commit_callbacks)
    assert revisions(chapter) == 1
    event = CoverageEvent.objects.get(user_id=ME, chapter_id=chapter.id, type="revision_done")
    assert (event.source, event.source_ref, event.value) == ("system", str(s.id), None)


def test_a_replayed_event_or_job_never_adds_a_second_revision(chapter, enrolled, django_capture_on_commit_callbacks):
    s = study(make_set(chapter, 5))
    announce(s, capture=django_capture_on_commit_callbacks)
    announce(s, capture=django_capture_on_commit_callbacks)  # the job ran twice
    payload = {
        "user_id": str(ME),
        "chapter_id": str(chapter.id),
        "session_id": str(s.id),
    }
    subscribers.on_chapter_pass_completed(**payload)  # the event replayed by hand
    assert revisions(chapter) == 1


def test_with_recall_counts_as_revision_off_coverage_is_left_alone(
    chapter, enrolled, django_capture_on_commit_callbacks
):
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"recall_counts_as_revision": False})
    seen = listen()
    announce(study(make_set(chapter, 5)), capture=django_capture_on_commit_callbacks)
    assert len(seen) == 1  # the pass is still announced
    assert revisions(chapter) == 0


@pytest.mark.parametrize("state", ["unenrolled", "archived", "other_scheme"])
def test_an_unenrolled_archived_or_other_scheme_student_never_raises(
    chapter, scheme, state, django_capture_on_commit_callbacks
):
    if state == "archived":
        Enrollment.objects.create(user_id=ME, scheme=scheme, level=scheme.level, status=Enrollment.Status.ARCHIVED)
    elif state == "other_scheme":
        from modules.syllabus.tests.helpers import switch_scheme

        new = switch_scheme(scheme)
        Enrollment.objects.create(user_id=ME, scheme=new, level=new.level)
    s = study(make_set(chapter, 5))
    announce(s, capture=django_capture_on_commit_callbacks)
    assert revisions(chapter) == 0
    assert not CoverageEvent.objects.filter(user_id=ME, type="revision_done").exists()


def test_a_vacation_does_not_stop_the_check(chapter, enrolled, django_capture_on_commit_callbacks):
    from datetime import date

    RecallSettings.objects.update_or_create(user_id=ME, defaults={"vacation_until": date(2026, 12, 31)})
    s = study(make_set(chapter, 5))
    assert [a.new for a in announce(s, capture=django_capture_on_commit_callbacks)] == [True]


def test_another_students_reviews_never_pass_my_chapter(chapter):
    other = uuid.uuid4()
    cards = [card(other, chapter_id=chapter.id, importance=1) for _ in range(5)]
    assert reads.pass_state(ME, chapter.id, now=NOW).set_size == 0 and len(cards) == 5
