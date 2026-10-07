"""
Buttons on a timer alert (X-01.1 W3.6, FR-N12): `act_from_notification` acts only on the phase the alert was about,
treats a tap close to the end as the student being there, and changes nothing when the timer moved since.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from modules.focus import services
from modules.focus.errors import InvalidInput
from modules.focus.models import ActiveTimer
from modules.tracking import selectors as tracking_selectors
from modules.tracking import services as tracking

pytestmark = pytest.mark.django_db
USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)
END = NOW + timedelta(minutes=25)


class Clock:
    def __init__(self, monkeypatch):
        self.now = NOW
        monkeypatch.setattr(tracking, "_now", lambda: self.now)

    def at(self, moment):
        self.now = moment


@pytest.fixture
def clock(monkeypatch):
    return Clock(monkeypatch)


def start(*, overtime=True, auto_break=True, auto_focus=False, **kw):
    services.update_settings(
        USER, {"overtime_enabled": overtime, "auto_start_breaks": auto_break, "auto_start_focus": auto_focus}
    )
    timer, _ = services.start(USER, client_id=uuid.uuid4(), **kw)
    return timer


def live() -> ActiveTimer | None:
    return ActiveTimer.objects.filter(pk=USER).first()


def tap(action, timer, *, version=None, issued_at=None):
    return services.act_from_notification(
        USER,
        action=action,
        client_id=timer.client_id,
        version=timer.version if version is None else version,
        issued_at=issued_at or END,
    )


def snapshot():
    return ActiveTimer.objects.filter(pk=USER).values().first()


def test_start_break_closes_an_overtime_round_at_the_tap_and_starts_the_break(clock):
    round_ = start()
    clock.at(END + timedelta(seconds=40))
    result = tap("start_break", round_)
    assert result.outcome == "done" and result.phase == "short_break"
    session = tracking_selectors.session_by_client_id(USER, round_.client_id)
    assert session is not None and session.status == "completed"
    assert live().client_id == uuid.uuid5(round_.client_id, "short_break-1")


def test_start_break_starts_a_waiting_break_when_breaks_do_not_begin_by_themselves(clock):
    round_ = start(overtime=False, auto_break=False)
    clock.at(END + timedelta(seconds=30))
    result = tap("start_break", round_)
    assert result.outcome == "done" and result.phase == "short_break"
    assert live().client_id == uuid.uuid5(round_.client_id, "alert-break")


def test_start_break_after_a_break_began_by_itself_reports_done_and_starts_nothing_new(clock):
    round_ = start(overtime=False)
    clock.at(END + timedelta(seconds=30))
    assert tap("start_break", round_).outcome == "done"
    assert live().client_id == uuid.uuid5(round_.client_id, "short_break-1")


def test_pause_and_resume_an_overtime_round(clock):
    round_ = start()
    clock.at(END + timedelta(seconds=20))
    paused = tap("pause", round_)
    assert paused.outcome == "done" and paused.paused and live().paused_at is not None
    clock.at(END + timedelta(minutes=3))
    assert tap("pause", live()).outcome == "already"
    resumed = services.act_from_notification(
        USER, action="resume", client_id=paused.client_id, version=paused.version, issued_at=END
    )
    assert resumed.outcome == "done" and live().paused_at is None
    assert tap("resume", live()).outcome == "already"


def test_a_stale_version_changes_nothing(clock):
    round_ = start()
    clock.at(END + timedelta(seconds=20))
    before = snapshot()
    assert tap("start_break", round_, version=round_.version + 1).outcome == "stale"
    assert snapshot() == before


def test_another_phase_is_stale_and_untouched(clock):
    start()
    clock.at(END + timedelta(seconds=20))
    other = ActiveTimer(client_id=uuid.uuid4(), version=1)
    before = snapshot()
    assert tap("pause", other).outcome == "stale" and snapshot() == before


def test_a_tap_long_after_the_end_cannot_vouch_for_presence_and_sends_the_student_to_the_app(clock):
    round_ = start()
    clock.at(END + timedelta(minutes=4))  # no heartbeat since the start, and the tap is outside the window
    result = tap("start_break", round_)
    assert result.outcome == "needs_app" and live().away_pending
    assert tracking_selectors.session_by_client_id(USER, round_.client_id) is None


def test_start_focus_after_a_break_keeps_the_subject_of_the_round_before(clock, scheme):
    from modules.syllabus.models import Subject

    subject = Subject.objects.get(key="taxation")
    round_ = start(overtime=False, subject_id=subject.id)
    clock.at(END)
    services.complete(USER)  # the student's screen reached zero: the break begins
    break_ = live()
    assert break_.phase == "short_break"
    clock.at(END + timedelta(minutes=5, seconds=30))
    result = tap("start_focus", break_)
    assert result.outcome == "done" and result.phase == "focus"
    assert live().subject_id == subject.id and live().round_number == 2
    assert live().client_id != round_.client_id


def test_start_focus_when_the_round_already_began_by_itself_is_already(clock):
    start(overtime=False, auto_focus=True)
    clock.at(END)
    services.complete(USER)
    break_ = live()
    clock.at(END + timedelta(minutes=4))
    services.sync(USER, alive=True)  # seen near the end of the break
    clock.at(END + timedelta(minutes=5, seconds=20))
    services.sync(USER)  # so round 2 begins by itself
    assert live().phase == "focus"
    result = services.act_from_notification(
        USER, action="start_focus", client_id=break_.client_id, version=break_.version, issued_at=clock.now
    )
    assert result.outcome == "already"


def test_start_focus_when_idle_is_stale_once_the_student_did_something_after_the_alert(clock):
    start(overtime=False)
    clock.at(END)
    services.complete(USER)
    break_ = live()
    clock.at(END + timedelta(minutes=6))
    services.sync(USER)  # the break ends while no one is there: the timer is idle, focus is next
    assert live() is None
    issued = END + timedelta(minutes=5, seconds=5)
    ok = services.act_from_notification(
        USER, action="start_focus", client_id=break_.client_id, version=break_.version, issued_at=issued
    )
    assert ok.outcome == "done"
    services.end(USER, save=False)  # the student throws that round away in the app
    again = services.act_from_notification(
        USER, action="start_focus", client_id=break_.client_id, version=break_.version, issued_at=issued
    )
    assert again.outcome == "stale" and live() is None


def test_an_unknown_action_is_refused():
    with pytest.raises(InvalidInput):
        services.act_from_notification(USER, action="explode", client_id=uuid.uuid4(), version=1, issued_at=NOW)
