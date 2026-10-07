"""
The weekly email (X-01.1 W3.5, FR-N13): Sunday 18:00 in the student's time zone, everyone with the category on, study
time, streak, coverage and revision due, skipped when there is nothing to say, at most once, retried when the mail
server fails, and never part of the push pipeline.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from modules.coverage.models import ChapterProgress, Enrollment
from modules.notifications import channels
from modules.notifications.models import Delivery, Notification, NotificationSettings, Preference
from modules.notifications.scheduling import sweep
from modules.notifications.services import settings as settings_service
from modules.notifications.tests.motivation_helpers import OTHER, USER
from modules.notifications.tests.tracker_bench import rollup
from modules.profiles.models import Profile
from modules.syllabus.models import Chapter

pytestmark = pytest.mark.django_db

PLANNED = datetime(2026, 10, 7, 9, 0, tzinfo=UTC)  # Wednesday
DUE = datetime(2026, 10, 11, 12, 30, tzinfo=UTC)  # Sunday 18:00 in India
AT = DUE + timedelta(seconds=40)
SUNDAY = date(2026, 10, 11)


@pytest.fixture(autouse=True)
def urls(settings):
    settings.NOTIFICATIONS_WEB_BASE_URL = "https://app.example.test"
    settings.NOTIFICATIONS_PUBLIC_BASE_URL = "https://api.example.test"


@pytest.fixture(autouse=True)
def student():
    Profile.objects.create(id=USER, email="student@example.com")
    plan(timezone="Asia/Kolkata", nudge_enabled=False)  # the daily nudge has its own tests; keep the counters clean
    study(minutes=90, days_ago=1)  # a week worth writing about unless a test says otherwise


def plan(user=USER, **changes):
    return settings_service.update_settings(user, changes or {"timezone": "Asia/Kolkata"}, now=PLANNED)


def study(*, minutes=60, days_ago=0, user=USER):
    rollup(user, SUNDAY - timedelta(days=days_ago), minutes)


def run(now=AT):
    return sweep.run_sweep(now=now)


def mails(fake_email):
    return fake_email.sent


def due_at(user=USER):
    return NotificationSettings.objects.get(user_id=user).next_weekly_at


# --- when ---------------------------------------------------------------------------------------------------------------


def test_the_first_sunday_is_planned_from_the_time_zone():
    assert due_at() == DUE


def test_nothing_goes_before_sunday_six():
    run(DUE - timedelta(minutes=1))
    assert not Notification.objects.exists()


def test_it_is_sent_at_six_on_sunday_with_the_one_click_headers(fake_email, fake_push):
    result = run()
    assert result.fired == 1
    (mail,) = mails(fake_email)
    assert mail.to == "student@example.com"
    assert mail.subject == "Your week: 1 h 30 min of study"
    assert "1 h 30 min across 1 day" in mail.text
    unsub = mail.headers["List-Unsubscribe"]
    assert unsub.startswith("<https://api.example.test/api/v1/notifications/unsubscribe/?t=") and unsub.endswith(">")
    assert mail.headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "https://app.example.test/unsubscribe?t=" in mail.html
    assert fake_push.sent == []  # email never touches the push pipeline


def test_it_is_recorded_once_and_the_next_one_is_a_week_away(fake_email):
    run()
    run(AT + timedelta(minutes=1))
    assert len(mails(fake_email)) == 1
    notification = Notification.objects.get(user_id=USER)
    assert notification.dedupe_key == "weekly:2026-W41" and notification.category == "progress"
    assert notification.title == "Your week in Artha" and notification.deep_link == "/app/tracker"
    row = Delivery.objects.get(notification=notification)
    assert (row.channel, row.status, row.device_id, row.counts_toward_cap) == ("email", "sent", None, False)
    assert due_at() == DUE + timedelta(days=7)


def test_a_student_in_new_york_gets_it_at_their_own_six():
    other = plan(OTHER, timezone="America/New_York")
    assert other.next_weekly_at == datetime(2026, 10, 11, 22, 0, tzinfo=UTC)


def test_changing_the_time_zone_moves_the_week():
    plan(timezone="America/New_York")
    assert due_at() == datetime(2026, 10, 11, 22, 0, tzinfo=UTC)


def test_other_setting_changes_leave_it_alone():
    plan(nudge_enabled=False)
    assert due_at() == DUE


def test_rows_without_a_time_are_healed_by_the_sweep():
    NotificationSettings.objects.filter(pk=USER).update(next_weekly_at=None)
    run(PLANNED)
    assert due_at() == DUE


# --- what ---------------------------------------------------------------------------------------------------------------


def test_coverage_revision_and_the_exam_are_in_the_email(fake_email, scheme):
    enrollment = Enrollment.objects.create(
        user_id=USER, scheme=scheme, level=scheme.level, exam_date=SUNDAY + timedelta(days=45)
    )
    ChapterProgress.objects.create(
        user_id=USER,
        enrollment=enrollment,
        chapter=Chapter.objects.filter(subject__scheme=scheme).first(),
        next_revision_due=SUNDAY,
    )
    run()
    (mail,) = mails(fake_email)
    assert "Due for revision: 1 chapter" in mail.text
    assert "Exam in: 45 days" in mail.text
    assert "Syllabus covered: 0%" in mail.text


def test_a_week_with_nothing_but_revision_due_is_still_sent(fake_email, scheme):
    from modules.tracking.models import DailyRollup

    DailyRollup.objects.all().delete()
    enrollment = Enrollment.objects.create(user_id=USER, scheme=scheme, level=scheme.level)
    ChapterProgress.objects.create(
        user_id=USER,
        enrollment=enrollment,
        chapter=Chapter.objects.filter(subject__scheme=scheme).first(),
        next_revision_due=SUNDAY - timedelta(days=2),
    )
    run()
    (mail,) = mails(fake_email)
    assert mail.subject == "Your week: 1 chapter waiting for revision"


def test_a_week_with_no_study_and_nothing_due_is_skipped_and_the_next_is_planned(fake_email):
    from modules.tracking.models import DailyRollup

    DailyRollup.objects.all().delete()
    result = run()
    assert (result.fired, result.skipped) == (0, 1)
    assert mails(fake_email) == [] and not Notification.objects.exists()
    assert due_at() == DUE + timedelta(days=7)


def test_study_outside_the_seven_days_does_not_count(fake_email):
    from modules.tracking.models import DailyRollup

    DailyRollup.objects.all().delete()
    study(minutes=60, days_ago=7)
    run()
    assert mails(fake_email) == []


# --- who ---------------------------------------------------------------------------------------------------------------


def test_turning_the_email_off_records_why_and_sends_nothing(fake_email):
    Preference.objects.create(user_id=USER, category="progress", channel="email", enabled=False)
    result = run()
    assert result.fired == 0 and mails(fake_email) == []
    row = Delivery.objects.get(channel="email")
    assert (row.status, row.suppress_reason) == ("suppressed", "preference")


def test_the_master_switch_covers_email_too(fake_email):
    plan(push_master=False)
    run()
    assert mails(fake_email) == []
    assert Delivery.objects.get(channel="email").suppress_reason == "preference"


def test_a_student_without_an_address_is_suppressed(fake_email):
    Profile.objects.filter(pk=USER).update(email="")
    run()
    assert mails(fake_email) == []
    assert Delivery.objects.get(channel="email").suppress_reason == "no_address"


def test_it_goes_to_students_who_never_registered_a_push_device(fake_email):
    run()
    assert len(mails(fake_email)) == 1


def test_each_student_gets_their_own(fake_email):
    Profile.objects.create(id=OTHER, email="other@example.com")
    plan(OTHER)
    study(user=OTHER, minutes=30, days_ago=2)
    run()
    assert sorted(m.to for m in mails(fake_email)) == ["other@example.com", "student@example.com"]


# --- switches and lateness ------------------------------------------------------------------------------------------------


def test_the_kill_switch_stops_the_step_and_leaves_the_week_due(fake_email, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = frozenset({"weekly_summary"})
    run()
    assert mails(fake_email) == [] and due_at() == DUE


def test_the_environment_switch_stops_the_step(fake_email, settings):
    settings.NOTIFICATIONS_ENABLED = False
    run()
    assert mails(fake_email) == [] and due_at() == DUE


def test_the_sending_flag_off_skips_the_week(fake_email, monkeypatch):
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    result = run()
    assert result.skipped == 1 and mails(fake_email) == []
    assert due_at() == DUE + timedelta(days=7)


def test_a_week_overdue_by_more_than_a_day_is_skipped_not_sent_late(fake_email):
    result = run(DUE + timedelta(hours=25))
    assert result.skipped == 1 and mails(fake_email) == []
    assert due_at() == DUE + timedelta(days=7)


def test_a_week_up_to_a_day_late_is_still_sent(fake_email):
    run(DUE + timedelta(hours=23))
    assert len(mails(fake_email)) == 1


# --- failures ----------------------------------------------------------------------------------------------------------


def test_a_failed_send_is_retried_in_fifteen_minutes_and_then_sent(fake_email):
    fake_email.script.append(channels.SendResult.failed("smtpexception"))
    result = run()
    assert (result.fired, result.failed) == (0, 1)
    row = Delivery.objects.get(channel="email")
    assert (row.status, row.error_code, row.attempt) == ("failed", "smtpexception", 1)
    assert abs(due_at() - (AT + timedelta(minutes=15))) < timedelta(seconds=2)

    run(AT + timedelta(minutes=16))
    row.refresh_from_db()
    assert (row.status, row.attempt) == ("sent", 2) and len(mails(fake_email)) == 2
    assert Notification.objects.count() == 1
    assert due_at() == DUE + timedelta(days=7)


def test_it_gives_up_after_three_attempts(fake_email):
    fake_email.default = channels.SendResult.failed("smtpexception")
    at = AT
    for _ in range(3):
        run(at)
        at += timedelta(minutes=16)
    assert len(mails(fake_email)) == 3
    assert Delivery.objects.get(channel="email").attempt == 3
    assert due_at() == DUE + timedelta(days=7)
    run(at)
    assert len(mails(fake_email)) == 3


def test_a_missing_mail_configuration_is_reported_and_retried_later(fake_email):
    fake_email.script.append(channels.ChannelNotConfigured("no sender"))
    result = run()
    assert result.failed == 1 and not Delivery.objects.exists()
    assert abs(due_at() - (AT + timedelta(minutes=15))) < timedelta(seconds=2)
    run(AT + timedelta(minutes=16))
    assert len(mails(fake_email)) == 2


def test_missing_links_are_reported_as_a_configuration_problem(fake_email, settings):
    settings.NOTIFICATIONS_WEB_BASE_URL = ""
    assert run().failed == 1 and mails(fake_email) == []


# --- the adapter ---------------------------------------------------------------------------------------------------------


def test_the_django_adapter_sends_multipart_with_the_headers(settings, mailoutbox):
    settings.NOTIFICATIONS_EMAIL_FROM = "Artha <hello@mail.example.test>"
    message = channels.EmailMessage(
        to="a@example.com", subject="Hi", text="plain", html="<p>rich</p>", headers={"List-Unsubscribe": "<https://x>"}
    )
    assert channels.DjangoEmailChannel().send(message).status is channels.SendStatus.SENT
    (mail,) = mailoutbox
    assert mail.to == ["a@example.com"] and mail.from_email == "Artha <hello@mail.example.test>"
    assert mail.body == "plain" and mail.alternatives[0][0] == "<p>rich</p>"
    assert mail.extra_headers["List-Unsubscribe"] == "<https://x>"


def test_the_django_adapter_needs_a_sender(settings):
    settings.NOTIFICATIONS_EMAIL_FROM = ""
    with pytest.raises(channels.ChannelNotConfigured):
        channels.DjangoEmailChannel().send(channels.EmailMessage(to="a@example.com", subject="s", text="t", html="h"))


def test_a_transport_error_is_a_failed_attempt_not_a_crash(settings, monkeypatch):
    from django.core.mail import EmailMultiAlternatives

    settings.NOTIFICATIONS_EMAIL_FROM = "hello@mail.example.test"

    def boom(self, fail_silently=False):
        raise ConnectionRefusedError("down")

    monkeypatch.setattr(EmailMultiAlternatives, "send", boom)
    result = channels.DjangoEmailChannel().send(
        channels.EmailMessage(to="a@example.com", subject="s", text="t", html="h")
    )
    assert result.status is channels.SendStatus.FAILED and result.error_code == "connectionrefusederror"


# --- unsubscribing end to end -------------------------------------------------------------------------------------------


def test_the_link_in_the_email_switches_the_email_off_for_next_week(fake_email, client):
    run()
    link = fake_email.sent[0].headers["List-Unsubscribe"].strip("<>")
    path = link.replace("https://api.example.test", "")
    assert client.post(path).status_code == 200
    assert Preference.objects.filter(user_id=USER, category="progress", channel="email", enabled=False).exists()

    rollup(USER, date(2026, 10, 17), 45)
    run(AT + timedelta(days=7))
    assert len(mails(fake_email)) == 1
    assert Delivery.objects.filter(channel="email", suppress_reason="preference").count() == 1
