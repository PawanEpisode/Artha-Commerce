"""
Away alerts end to end (PRD X-01.2, ERD X-01.2):
- Server-driven "Still studying?" check for stopwatch when quiet > 90s
- Rescheduling when user was active meanwhile
- Page alive skip when tab is alive within 90s
- Still studying and Pause action buttons on desktop Chromium and Android
- Lazy settle into paused state when unanswered after 120s with follow-up push
- Strict flag gating on away_alerts
"""

import json
from datetime import timedelta

import pytest

from modules.notifications.domain.enums import JobKind, JobStatus, SkipReason
from modules.notifications.models import ScheduledJob
from modules.notifications.scheduling import jobs
from modules.notifications.services import actions
from modules.notifications.tests.helpers import register
from modules.notifications.tests.tracker_bench import NOW, USER, Tracker
from modules.tracking.models import ActiveStopwatch, TrackerSettings

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def away_alerts_on(monkeypatch):
    """Enable all notification flags including away_alerts."""
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: True)


@pytest.fixture(autouse=True)
def android():
    return register(USER, platform="android", browser="chrome").device


@pytest.fixture
def tracker(monkeypatch, django_capture_on_commit_callbacks):
    return Tracker(monkeypatch, django_capture_on_commit_callbacks)


def idle_jobs(user=USER):
    return list(ScheduledJob.objects.filter(user_id=user, kind=JobKind.STOPWATCH_IDLE).order_by("expected_version"))


def idle_end_jobs(user=USER):
    return list(ScheduledJob.objects.filter(user_id=user, kind=JobKind.STOPWATCH_IDLE_END).order_by("expected_version"))


def sent_payloads(fake_push) -> list[dict]:
    return [json.loads(message.body) for _, message in fake_push.sent]


def tokens(fake_push, index=-1) -> dict[str, str]:
    return {a["id"]: a["token"] for a in sent_payloads(fake_push)[index]["actions"]}


def test_starting_stopwatch_plans_idle_job(tracker, fake_queue):
    sw = tracker.start()
    (job,) = idle_jobs()
    assert (job.user_id, job.subject_key, job.expected_version) == (USER, str(sw.client_id), sw.version)
    assert job.fire_at == NOW + timedelta(minutes=10)
    assert job.status == JobStatus.PENDING
    assert job.context.get("idle_minutes") == 10
    assert any(item[0] == job.id for item in fake_queue.published)


def test_flag_off_plans_no_idle_job(tracker, monkeypatch):
    monkeypatch.setattr(
        "modules.notifications.flags.flag_enabled",
        lambda name, *a, **k: False if name == "away_alerts" else True,
    )
    tracker.start()
    assert idle_jobs() == []


def test_idle_minutes_zero_plans_no_idle_job(tracker):
    settings = TrackerSettings.objects.get_or_create(pk=USER)[0]
    settings.idle_minutes = 0
    settings.save()

    tracker.start()
    assert idle_jobs() == []


def test_page_alive_skips_push(tracker, fake_push):
    tracker.start()
    tracker.advance(minutes=9, seconds=30)
    tracker.sync(alive=True)
    tracker.advance(seconds=30)  # at 10m; page seen 30s ago (< 90s)

    (job,) = idle_jobs()
    result = jobs.fire_job(job.id, now=tracker.now)
    assert result.outcome is jobs.FireOutcome.SKIPPED
    assert result.reason == SkipReason.PAGE_ALIVE.value
    assert fake_push.sent == []
    assert idle_end_jobs() == []


def test_user_active_reschedules_idle_job(tracker, fake_push, fake_queue):
    tracker.start()
    tracker.advance(minutes=8)
    tracker.sync(active=True)  # user was active at 8m
    tracker.advance(minutes=2)  # at 10m: original fire_at

    (job,) = idle_jobs()
    result = jobs.fire_job(job.id, now=tracker.now)
    assert result.outcome is jobs.FireOutcome.RESCHEDULED

    job.refresh_from_db()
    assert job.status == JobStatus.PENDING
    assert job.fire_at == NOW + timedelta(minutes=8 + 10)  # rescheduled to 18m
    assert fake_push.sent == []
    assert idle_end_jobs() == []


def test_quiet_stopwatch_pushes_still_studying_and_plans_idle_end(tracker, fake_push):
    tracker.start()
    tracker.advance(minutes=10)  # quiet for 10 minutes

    (job,) = idle_jobs()
    result = jobs.fire_job(job.id, now=tracker.now)
    assert result.outcome is jobs.FireOutcome.NOTIFIED
    assert result.delivery == "sent"

    payloads = sent_payloads(fake_push)
    assert len(payloads) == 1
    assert payloads[0]["title"] == "Still studying?"
    action_ids = [a["id"] for a in payloads[0]["actions"]]
    assert action_ids == ["still_studying", "pause"]

    (end_job,) = idle_end_jobs()
    assert end_job.fire_at == tracker.now + timedelta(seconds=120)
    assert end_job.status == JobStatus.PENDING

    sw = ActiveStopwatch.objects.filter(pk=USER).first()
    assert sw.idle_pending is True
    assert sw.idle_prompted_at == tracker.now


def test_student_taps_still_studying_clears_idle_pending(tracker, fake_push):
    tracker.start()
    tracker.advance(minutes=10)
    jobs.fire_job(idle_jobs()[0].id, now=tracker.now)

    toks = tokens(fake_push)
    assert "still_studying" in toks

    tracker.advance(seconds=30)
    tap_result = actions.tap(toks["still_studying"], now=tracker.now)
    assert tap_result.outcome == "done"

    sw = ActiveStopwatch.objects.filter(pk=USER).first()
    assert sw.idle_pending is False
    assert sw.paused_at is None


def test_student_taps_pause_offers_resume_button(tracker, fake_push):
    tracker.start()
    tracker.advance(minutes=10)
    jobs.fire_job(idle_jobs()[0].id, now=tracker.now)

    toks = tokens(fake_push)
    assert "pause" in toks

    tracker.advance(seconds=20)
    tap_result = actions.tap(toks["pause"], now=tracker.now)
    assert tap_result.outcome == "done"
    assert [a.id for a in tap_result.actions] == ["resume"]

    sw = ActiveStopwatch.objects.filter(pk=USER).first()
    assert sw.paused_at is not None


def test_unanswered_idle_settles_and_pushes_stopwatch_paused(tracker, fake_push):
    tracker.start()
    tracker.advance(minutes=10)
    jobs.fire_job(idle_jobs()[0].id, now=tracker.now)

    # 120s passes with no answer
    tracker.advance(seconds=120)
    (end_job,) = idle_end_jobs()
    result = jobs.fire_job(end_job.id, now=tracker.now)
    assert result.outcome is jobs.FireOutcome.NOTIFIED
    assert result.delivery == "sent"

    payloads = sent_payloads(fake_push)
    assert len(payloads) == 2
    paused_push = payloads[1]
    assert paused_push["title"] == "Stopwatch paused"
    assert "We stopped counting when you went quiet" in paused_push["body"]
    assert [a["id"] for a in paused_push["actions"]] == ["resume"]

    sw = ActiveStopwatch.objects.filter(pk=USER).first()
    assert sw.paused_at is not None
    assert sw.idle_pending is False

    # Student taps resume from push
    resume_tok = paused_push["actions"][0]["token"]
    tracker.advance(minutes=5)
    tap_result = actions.tap(resume_tok, now=tracker.now)
    assert tap_result.outcome == "done"

    sw = ActiveStopwatch.objects.filter(pk=USER).first()
    assert sw.paused_at is None


def test_desktop_chromium_gets_buttons(tracker, fake_push):
    register(USER, platform="windows", browser="chrome")
    register(USER, platform="macos", browser="edge")
    register(USER, platform="ios", browser="safari")
    register(USER, platform="linux", browser="firefox")

    tracker.start()
    tracker.advance(minutes=10)
    jobs.fire_job(idle_jobs()[0].id, now=tracker.now)

    payloads = sent_payloads(fake_push)
    # android (fixture) + windows chrome + macos edge get buttons (3 devices)
    # ios safari + linux firefox get no buttons (2 devices)
    by_actions = sorted(len(p["actions"]) for p in payloads)
    assert by_actions == [0, 0, 2, 2, 2]
