"""
The daily slot (X-01.1 W3.4): at the student's nudge time exactly one push goes out, and it is an exam milestone, revision
that is due, or the daily thought, in that order. Same machinery as the nudge (claim, policy, cap, quiet hours).
"""

import json
from datetime import UTC, date, datetime, time, timedelta

import pytest

from modules.coverage.models import ChapterProgress, Enrollment
from modules.notifications.domain.enums import DeliveryStatus
from modules.notifications.models import Delivery, MessageShown, Notification, Preference, ScheduledJob
from modules.notifications.scheduling import sweep
from modules.notifications.services import settings as settings_service
from modules.notifications.tests.helpers import register
from modules.notifications.tests.motivation_helpers import USER, library
from modules.profiles.models import LastVisit
from modules.syllabus.models import Chapter

pytestmark = pytest.mark.django_db

PLANNED = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
DUE = datetime(2026, 10, 7, 4, 30, tzinfo=UTC)  # Wednesday 10:00 in India
AT = DUE + timedelta(seconds=40)
TODAY = date(2026, 10, 7)


@pytest.fixture(autouse=True)
def device():
    return register(USER, platform="android", browser="chrome").device


@pytest.fixture(autouse=True)
def lines():
    return library(12)


def plan(**changes):
    return settings_service.update_settings(USER, changes, now=PLANNED)


def run(now=AT):
    return sweep.run_sweep(now=now)


def pushed(fake_push):
    return [json.loads(message.body) for _, message in fake_push.sent]


def enroll(scheme, *, days_left=None, due=()):
    """An active enrolment with `days_left` to the exam and the named chapters due for revision today."""
    exam = TODAY + timedelta(days=days_left) if days_left is not None else None
    enrollment = Enrollment.objects.create(user_id=USER, scheme=scheme, level=scheme.level, exam_date=exam)
    for key in due:
        ChapterProgress.objects.create(
            user_id=USER,
            enrollment=enrollment,
            chapter=Chapter.objects.get(subject__scheme=scheme, key=key),
            next_revision_due=TODAY,
        )
    return enrollment


def events():
    return sorted(Notification.objects.filter(user_id=USER).values_list("event", flat=True))


# --- the exam milestone ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("days_left", [60, 30, 14, 7, 3, 1])
def test_a_milestone_day_sends_the_exam_push_and_no_thought(fake_push, scheme, days_left):
    enroll(scheme, days_left=days_left)
    plan()
    assert run().fired == 1
    (payload,) = pushed(fake_push)
    assert payload["tag"] == f"exam:{days_left}" and payload["url"].split("?")[0] == "/app"
    assert events() == ["exam_milestone"] and not MessageShown.objects.exists()
    n = Notification.objects.get()
    assert (n.category, n.priority, n.dedupe_key) == ("exam", 2, f"exam:{days_left}")


def test_other_days_before_the_exam_send_the_thought(fake_push, scheme):
    enroll(scheme, days_left=29)
    plan()
    run()
    assert events() == ["daily_nudge"] and pushed(fake_push)[0]["title"] == "A thought for today"


def test_a_milestone_wins_over_revision_and_the_thought_so_there_is_one_push(fake_push, scheme):
    enroll(scheme, days_left=7, due=["gst-itc", "companies-act"])
    plan()
    run()
    assert len(pushed(fake_push)) == 1 and events() == ["exam_milestone"]


def test_the_exam_push_is_sent_even_when_the_student_opened_the_app_today(fake_push, scheme):
    enroll(scheme, days_left=14)
    LastVisit.objects.create(user_id=USER, path="/app", search="", visited_at=DUE - timedelta(hours=2))
    plan()
    run()
    assert [p["tag"] for p in pushed(fake_push)] == ["exam:14"]


def test_a_milestone_goes_out_once_even_when_the_sweep_runs_again(fake_push, scheme):
    enroll(scheme, days_left=30)
    plan()
    run()
    run(AT + timedelta(minutes=1))
    run(AT + timedelta(hours=1))
    assert len(pushed(fake_push)) == 1 and Notification.objects.count() == 1


def test_the_next_day_is_a_different_number_so_no_second_milestone(fake_push, scheme):
    enroll(scheme, days_left=30)
    plan()
    run()
    run(DUE + timedelta(days=1, seconds=40))  # 29 days left
    assert events() == ["daily_nudge", "exam_milestone"]


# --- revision -----------------------------------------------------------------------------------------------------------


def test_chapters_due_replace_the_thought_with_a_revision_push(fake_push, scheme):
    enroll(scheme, due=["gst-itc", "companies-act"])
    plan()
    run()
    (payload,) = pushed(fake_push)
    assert payload["title"] == "Revision due"
    assert payload["body"].startswith("2 chapters are due for revision, starting with ")
    assert payload["url"].split("?")[0] == "/app/revision" and payload["tag"] == "revision:2026-10-07"
    assert events() == ["revision_due"] and not MessageShown.objects.exists()


def test_revision_starts_with_the_heaviest_overdue_chapter(fake_push, scheme):
    enrollment = enroll(scheme, due=["gst-itc", "companies-act"])
    ChapterProgress.objects.filter(enrollment=enrollment, chapter__key="companies-act").update(
        next_revision_due=TODAY - timedelta(days=4)
    )
    plan()
    run()
    assert "starting with Companies Act" in pushed(fake_push)[0]["body"]


def test_a_student_with_nothing_due_and_no_milestone_gets_the_thought(fake_push, scheme):
    enroll(scheme, days_left=100)
    plan()
    run()
    assert events() == ["daily_nudge"]


def test_a_student_with_no_enrolment_gets_the_thought(fake_push):
    plan()
    run()
    assert events() == ["daily_nudge"] and len(pushed(fake_push)) == 1


def test_revision_is_skipped_when_the_student_already_opened_the_app_and_the_thought_is_not_sent_instead(
    fake_push, scheme
):
    enroll(scheme, due=["gst-itc"])
    LastVisit.objects.create(user_id=USER, path="/app", search="", visited_at=DUE - timedelta(hours=2))
    plan()
    run()
    assert pushed(fake_push) == []
    (delivery,) = Delivery.objects.all()
    assert (delivery.status, delivery.suppress_reason) == ("suppressed", "visited_today")
    assert events() == ["revision_due"] and not MessageShown.objects.exists()


def test_revision_that_was_displaced_by_a_milestone_is_offered_again_the_next_day(fake_push, scheme):
    enrollment = enroll(scheme, days_left=1, due=["gst-itc"])
    plan()
    run()
    assert events() == ["exam_milestone"]
    Enrollment.objects.filter(pk=enrollment.pk).update(exam_date=TODAY + timedelta(days=40))
    ChapterProgress.objects.update(next_revision_due=TODAY)  # still due tomorrow
    run(DUE + timedelta(days=1, seconds=40))
    assert events() == ["exam_milestone", "revision_due"]


# --- the student's choices and the switches --------------------------------------------------------------------------


def test_with_the_exam_category_off_for_push_the_next_best_push_goes_out_instead(fake_push, scheme):
    enroll(scheme, days_left=30, due=["gst-itc"])
    Preference.objects.create(user_id=USER, category="exam", channel="push", enabled=False)
    plan()
    run()
    assert events() == ["revision_due"]


def test_with_both_off_the_thought_still_arrives(fake_push, scheme):
    enroll(scheme, days_left=30, due=["gst-itc"])
    for category in ("exam", "revision"):
        Preference.objects.create(user_id=USER, category=category, channel="push", enabled=False)
    plan()
    run()
    assert events() == ["daily_nudge"] and len(pushed(fake_push)) == 1


def test_the_kill_switch_for_an_event_moves_the_slot_to_the_next_one(fake_push, scheme, settings):
    enroll(scheme, days_left=30, due=["gst-itc"])
    plan()
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"exam_milestone"})
    run()
    assert events() == ["revision_due"]


def test_quiet_hours_hold_the_exam_push_until_they_end(fake_push, scheme):
    enroll(scheme, days_left=7)
    plan(nudge_time=time(6, 0))  # inside the default quiet window, 22:00 to 07:00
    due = datetime(2026, 10, 7, 0, 30, tzinfo=UTC)
    run(due + timedelta(seconds=40))
    assert fake_push.sent == []
    assert Notification.objects.get().deliveries.get().status == DeliveryStatus.QUEUED
    job = ScheduledJob.objects.get(kind="deliver_deferred")
    assert job.fire_at == datetime(2026, 10, 7, 1, 30, tzinfo=UTC)  # 07:00 in India
    run(job.fire_at + timedelta(minutes=1))
    assert [p["tag"] for p in pushed(fake_push)] == ["exam:7"]


def test_switching_off_the_daily_nudge_event_stops_the_whole_slot(fake_push, scheme, settings):
    enroll(scheme, days_left=7, due=["gst-itc"])
    plan()
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"daily_nudge"})
    result = run()
    assert (result.fired, result.skipped) == (0, 0) and fake_push.sent == [] and not Notification.objects.exists()


def test_the_sending_flag_off_sends_nothing_and_creates_nothing(fake_push, scheme, monkeypatch):
    enroll(scheme, days_left=30)
    plan()
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    run()
    assert pushed(fake_push) == [] and not Notification.objects.exists()


# --- the exam date falls back to the chosen term -----------------------------------------------------------------------


def test_the_countdown_uses_the_term_start_when_the_student_set_no_exam_date(fake_push, scheme):
    from modules.syllabus.models import ExamTerm

    term = ExamTerm.objects.create(
        level=scheme.level, code="2026-12", name="Dec 2026", exam_start=TODAY + timedelta(days=30)
    )
    Enrollment.objects.create(user_id=USER, scheme=scheme, level=scheme.level, target_term=term)
    plan()
    run()
    assert events() == ["exam_milestone"]
    assert "One month left" in pushed(fake_push)[0]["body"]
