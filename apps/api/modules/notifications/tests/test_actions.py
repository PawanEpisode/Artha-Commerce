"""
Buttons on timer alerts end to end (X-01.1 W3.6, FR-N12): the alert to an Android device carries one-time tokens, a
tap changes the timer through `focus` without a sign-in, and a token works once, for ten minutes, for one timer phase.
"""

import json
import logging
import threading
import uuid
from datetime import timedelta

import pytest
from django.db import connection

from modules.focus.models import ActiveTimer
from modules.notifications.domain import actions as buttons
from modules.notifications.errors import ActionUnavailable, NotificationsDisabled
from modules.notifications.models import ActionToken, Delivery, ScheduledJob
from modules.notifications.scheduling import jobs
from modules.notifications.selectors.export import export_all
from modules.notifications.services import actions, retention
from modules.notifications.services.erasure import delete_all_for_user
from modules.notifications.tests.helpers import register
from modules.notifications.tests.timer_bench import FOCUS_END, USER
from modules.tracking import selectors as tracking_selectors

pytestmark = pytest.mark.django_db
URL = "/api/v1/notifications/actions/"
TAP_AT = FOCUS_END + timedelta(seconds=30)


@pytest.fixture(autouse=True)
def android():
    return register(USER, platform="android", browser="chrome").device


def fire_end(bench, timer, at=FOCUS_END):
    job = ScheduledJob.objects.get(subject_key=str(timer.client_id), expected_version=timer.version)
    return jobs.fire_job(job.id, now=at)


def sent_payloads(fake_push) -> list[dict]:
    return [json.loads(message.body) for _, message in fake_push.sent]


def tokens(fake_push, index=-1) -> dict[str, str]:
    return {a["id"]: a["token"] for a in sent_payloads(fake_push)[index]["actions"]}


def alert(bench, fake_push, **start) -> tuple[ActiveTimer, dict[str, str]]:
    """A round runs to its target and its alert goes out. Returns the round and the button tokens it carried."""
    timer = bench.start(overtime=start.pop("overtime", True), **start)
    fire_end(bench, timer)
    return timer, tokens(fake_push)


def tap(bench, token, at=TAP_AT):
    bench.set(at)
    with bench._capture(execute=True):
        return actions.tap(token, now=at)


def row(timer):
    return ActiveTimer.objects.filter(pk=USER).values().first()


# --- the alert -----------------------------------------------------------------------------------------------------


def test_an_overtime_alert_to_android_carries_start_break_and_pause_with_one_time_tokens(bench, fake_push):
    _, found = alert(bench, fake_push)
    payload = sent_payloads(fake_push)[0]
    assert [(a["id"], a["title"]) for a in payload["actions"]] == [("start_break", "Start break"), ("pause", "Pause")]
    assert all(buttons.well_formed(t) for t in found.values())
    stored = list(ActionToken.objects.values("action", "token_hash", "expires_at", "user_id"))
    assert {r["action"] for r in stored} == {"start_break", "pause"}
    assert all(r["expires_at"] == FOCUS_END + timedelta(minutes=10) and r["user_id"] == USER for r in stored)
    assert {r["token_hash"] for r in stored} == {buttons.hash_token(t) for t in found.values()}
    assert not any(t in str(stored) for t in found.values())  # only the hash is kept


def test_only_android_devices_get_buttons(bench, fake_push):
    register(USER, platform="ios", browser="safari", display_mode="standalone")
    register(USER, platform="windows", browser="chrome")
    alert(bench, fake_push)
    by_actions = sorted(len(p["actions"]) for p in sent_payloads(fake_push))
    assert by_actions == [0, 0, 2]
    assert ActionToken.objects.count() == 2  # minted once for the send, not per device


def test_no_device_on_android_means_no_tokens(bench, fake_push, android):
    android.platform = "macos"
    android.save()
    alert(bench, fake_push)
    assert sent_payloads(fake_push)[0]["actions"] == [] and not ActionToken.objects.exists()


def test_a_round_whose_break_begins_by_itself_has_no_buttons(bench, fake_push):
    bench.start(overtime=False)
    timer = bench.timer
    bench.heartbeat()
    fire_end(bench, timer)
    assert sent_payloads(fake_push)[0]["actions"] == []


def test_the_break_over_alert_offers_the_next_round(bench, fake_push):
    timer = bench.start(overtime=False)
    bench.set(FOCUS_END)
    bench.complete()
    brk = bench.timer
    fire_end(bench, brk, at=FOCUS_END + timedelta(minutes=5))
    payload = sent_payloads(fake_push)[-1]
    assert [(a["id"], a["title"]) for a in payload["actions"]] == [("start_focus", "Start round 2")]
    assert timer.client_id != brk.client_id


# --- a tap ---------------------------------------------------------------------------------------------------------


def test_start_break_saves_the_round_and_starts_the_break_without_opening_the_app(bench, fake_push):
    timer, found = alert(bench, fake_push)
    result = tap(bench, found["start_break"])
    assert result.outcome == "done" and result.title == "Break started"
    assert result.tag == f"timer:{timer.client_id}" and result.url.startswith("/app/focus?n=")
    assert bench.timer.phase == "short_break"
    assert tracking_selectors.session_by_client_id(USER, timer.client_id).status == "completed"
    assert Delivery.objects.get(channel="push").clicked_at == TAP_AT  # the tap is engagement


def test_pause_then_resume_from_the_confirmation(bench, fake_push):
    _, found = alert(bench, fake_push)
    paused = tap(bench, found["pause"])
    assert paused.outcome == "done" and bench.timer.paused_at is not None
    (resume,) = paused.actions
    assert resume.id == "resume" and resume.title == "Resume" and buttons.well_formed(resume.token)
    resumed = tap(bench, resume.token, at=TAP_AT + timedelta(minutes=2))
    assert resumed.outcome == "done" and bench.timer.paused_at is None and resumed.actions == []


def test_a_replayed_token_is_refused_and_changes_nothing(bench, fake_push):
    _, found = alert(bench, fake_push)
    tap(bench, found["pause"])
    before = row(bench.timer)
    with pytest.raises(ActionUnavailable):
        tap(bench, found["pause"], at=TAP_AT + timedelta(seconds=5))
    assert row(bench.timer) == before


def test_an_expired_token_is_refused(bench, fake_push):
    timer, found = alert(bench, fake_push)
    before = row(timer)
    with pytest.raises(ActionUnavailable):
        tap(bench, found["start_break"], at=FOCUS_END + timedelta(minutes=10))
    assert row(timer) == before and ActionToken.objects.filter(used_at__isnull=False).count() == 0


@pytest.mark.parametrize("token", ["", "short", "A" * 43, "A" * 42 + "!", None])
def test_malformed_and_unknown_tokens_are_refused_the_same_way(bench, fake_push, token):
    alert(bench, fake_push)
    with pytest.raises(ActionUnavailable):
        tap(bench, token)


def test_a_stale_token_changes_nothing_once_the_timer_moved(bench, fake_push):
    timer, found = alert(bench, fake_push)
    bench.set(FOCUS_END + timedelta(seconds=10))
    bench.complete()  # the app is open at the end
    bench.pause(version=timer.version)  # and the student pauses there
    before = row(timer)
    result = tap(bench, found["start_break"])
    assert result.outcome == "stale" and result.title == "Nothing changed"
    assert row(timer) == before and ActionToken.objects.get(action="start_break").used_at == TAP_AT


def test_a_token_acts_only_for_its_own_student(bench, fake_push, monkeypatch, django_capture_on_commit_callbacks):
    from modules.notifications.tests.timer_bench import Bench

    other = Bench(monkeypatch, django_capture_on_commit_callbacks, user=uuid.uuid4())
    other.set(bench.now)
    theirs = other.start(overtime=True)
    _, found = alert(bench, fake_push)
    their_row = ActiveTimer.objects.filter(pk=other.user).values().first()
    tap(bench, found["pause"])
    assert ActiveTimer.objects.filter(pk=other.user).values().first() == their_row
    assert theirs.paused_at is None and bench.timer.paused_at is not None


def test_a_tap_long_after_the_end_asks_for_the_app(bench, fake_push):
    timer, found = alert(bench, fake_push)
    result = tap(bench, found["start_break"], at=FOCUS_END + timedelta(minutes=4))
    assert result.outcome == "needs_app" and result.title == "Open the app"
    assert tracking_selectors.session_by_client_id(USER, timer.client_id) is None


def test_start_the_next_round_from_the_break_over_alert(bench, fake_push):
    bench.start(overtime=False)
    bench.set(FOCUS_END)
    bench.complete()
    brk = bench.timer
    fire_end(bench, brk, at=FOCUS_END + timedelta(minutes=5))
    token = tokens(fake_push)["start_focus"]
    result = tap(bench, token, at=FOCUS_END + timedelta(minutes=5, seconds=20))
    assert result.outcome == "done" and bench.timer.phase == "focus" and bench.timer.round_number == 2


# --- switches ------------------------------------------------------------------------------------------------------


def test_the_button_kill_switch_removes_buttons_and_refuses_taps(bench, fake_push, settings):
    _, found = alert(bench, fake_push)
    settings.NOTIFICATIONS_DISABLED_EVENTS = [buttons.KILL_SWITCH]
    with pytest.raises(NotificationsDisabled):
        tap(bench, found["pause"])
    assert ActionToken.objects.filter(used_at__isnull=False).count() == 0
    assert bench.timer.paused_at is None  # the refused tap changed nothing


def test_no_buttons_are_minted_while_the_kill_switch_is_on(bench, fake_push, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = [buttons.KILL_SWITCH]
    alert(bench, fake_push)
    assert sent_payloads(fake_push)[0]["actions"] == [] and not ActionToken.objects.exists()


def test_the_master_switch_refuses_taps(bench, fake_push, settings):
    _, found = alert(bench, fake_push)
    settings.NOTIFICATIONS_ENABLED = False
    with pytest.raises(NotificationsDisabled):
        tap(bench, found["pause"])


def test_the_sending_flag_refuses_taps(bench, fake_push, monkeypatch):
    _, found = alert(bench, fake_push)
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: False)
    with pytest.raises(NotificationsDisabled):
        tap(bench, found["pause"])
    assert bench.timer.paused_at is None


# --- the endpoint --------------------------------------------------------------------------------------------------


def post(client, body):
    return client.post(URL, body, content_type="application/json")


def test_the_endpoint_needs_no_sign_in_and_answers_the_confirmation(bench, fake_push, client, clock):
    _, found = alert(bench, fake_push)
    bench.set(clock.set(TAP_AT))
    r = post(client, {"token": found["pause"]})
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "done" and body["notification"]["title"] == "Timer paused"
    assert [a["id"] for a in body["notification"]["actions"]] == ["resume"]
    assert set(body["notification"]) == {"title", "body", "tag", "url", "actions"}


def test_every_refusal_has_the_same_answer(bench, fake_push, client, clock):
    _, found = alert(bench, fake_push)
    bench.set(clock.set(TAP_AT))
    assert post(client, {"token": found["pause"]}).status_code == 200
    answers = [
        post(client, {"token": found["pause"]}),  # used
        post(client, {"token": "Z" * 43}),  # unknown
        post(client, {"token": "nope"}),  # malformed
        post(client, {}),  # missing
    ]
    clock.set(FOCUS_END + timedelta(minutes=11))
    answers.append(post(client, {"token": found["start_break"]}))  # expired
    assert {r.status_code for r in answers} == {400}
    assert len({json.dumps(r.json(), sort_keys=True) for r in answers}) == 1
    assert answers[0].json()["error"]["code"] == "action_unavailable"


def test_the_endpoint_is_throttled(client, settings):
    for _ in range(30):
        assert post(client, {"token": "Z" * 43}).status_code == 400
    assert post(client, {"token": "Z" * 43}).status_code == 429


def test_only_post_is_allowed(client):
    assert client.get(URL).status_code == 405


def test_no_token_reaches_the_logs(bench, fake_push, client, clock, caplog):
    caplog.set_level(logging.DEBUG)
    _, found = alert(bench, fake_push)
    bench.set(clock.set(TAP_AT))
    post(client, {"token": found["pause"]})
    post(client, {"token": found["pause"]})
    text = caplog.text + " ".join(str(getattr(r, "push", "")) for r in caplog.records)
    assert "push_action" in text and "push_action_rejected" in text
    assert not any(token in text for token in found.values())


# --- concurrency, retention, data rights ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@pytest.mark.skipif(connection.vendor != "postgresql", reason="Row locks need PostgreSQL (CI runs it)")
def test_two_simultaneous_taps_act_once(bench, fake_push):
    _, found = alert(bench, fake_push)
    barrier, outcomes = threading.Barrier(2), []

    def use():
        from django.db import connection as conn

        barrier.wait()
        try:
            actions.consume(found["pause"], now=TAP_AT)
            outcomes.append("used")
        except ActionUnavailable:
            outcomes.append("refused")
        finally:
            conn.close()

    threads = [threading.Thread(target=use) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == ["refused", "used"]


def test_a_second_use_in_a_row_is_refused_by_the_update_itself(bench, fake_push):
    _, found = alert(bench, fake_push)
    assert actions.consume(found["pause"], now=TAP_AT).used_at == TAP_AT
    with pytest.raises(ActionUnavailable):
        actions.consume(found["pause"], now=TAP_AT)


def test_retention_prunes_tokens_a_day_after_they_expire(bench, fake_push):
    alert(bench, fake_push)
    expiry = FOCUS_END + timedelta(minutes=10)
    assert retention.prune(now=expiry + timedelta(hours=23)).action_tokens == 0
    result = retention.prune(now=expiry + timedelta(days=1, seconds=1))
    assert result.action_tokens == 2 and not ActionToken.objects.exists()
    assert retention.prune(now=expiry + timedelta(days=2)).action_tokens == 0  # a re-run is a no-op


def test_export_lists_buttons_without_secrets_and_the_eraser_removes_them(bench, fake_push):
    _, found = alert(bench, fake_push)
    data = export_all(USER)["notification_buttons"]
    assert {b["action"] for b in data} == {"start_break", "pause"}
    assert "token_hash" not in str(data) and not any(t in str(data) for t in found.values())
    counts = delete_all_for_user(USER)
    assert counts["action_tokens"] == 2 and not ActionToken.objects.exists()
