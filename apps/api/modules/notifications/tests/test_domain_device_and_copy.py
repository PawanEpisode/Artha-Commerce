from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications.domain.catalogue import UnknownEvent
from modules.notifications.domain.copy import BODY_LIMIT, TITLE_LIMIT, build_copy
from modules.notifications.domain.device_health import Health, on_failure, on_success
from modules.notifications.domain.enums import RevokeReason

T0 = datetime(2026, 3, 1, tzinfo=UTC)


@pytest.mark.parametrize("status", [404, 410])
def test_gone_revokes_at_once(status):
    assert on_failure(Health(), T0, status).revoke is RevokeReason.GONE


def test_transient_failures_need_count_and_age():
    h = Health()
    for i in range(5):
        change = on_failure(h, T0 + timedelta(hours=i), 503)
        h = change.health
        assert change.revoke is None  # five failures but only hours old
    assert h.consecutive_failures == 5 and h.first_failure_at == T0
    assert on_failure(h, T0 + timedelta(days=7), 503).revoke is RevokeReason.FAILURES


def test_old_but_few_failures_do_not_revoke():
    h = on_failure(Health(), T0, 500).health
    assert on_failure(h, T0 + timedelta(days=30), 500).revoke is None


def test_success_clears_the_run():
    assert on_success() == Health()


CTX = {"client_id": "c1", "minutes": 25, "round_number": 2}


def test_timer_end_copy():
    c = build_copy("timer_end", {**CTX, "subject_name": "Law", "break_minutes": 5})
    assert c.title == "Round 2 done" and "25 minutes on Law" in c.body and "Take 5" in c.body
    assert c.deep_link == "/app/focus" and c.tag == "timer:c1"


def test_timer_end_overtime_says_target_reached_not_done():
    c = build_copy("timer_end", {**CTX, "overtime": True})
    assert c.title == "Round target reached" and "still running" in c.body


def test_singular_minute_and_limits():
    assert "1 minute." in build_copy("timer_end", {**CTX, "minutes": 1}).body
    long = build_copy("timer_end", {**CTX, "subject_name": "x" * 300})
    assert len(long.title) <= TITLE_LIMIT and len(long.body) <= BODY_LIMIT


def test_break_over_and_unknown():
    assert build_copy("break_over", {"client_id": "c1", "next_round": 3}).body == "Ready for round 3?"
    with pytest.raises(UnknownEvent):
        build_copy("plan_ready", {})  # an event whose copy is not written yet cannot be sent unreviewed


def test_daily_nudge_copy_is_the_library_line_whole_and_links_home():
    c = build_copy("daily_nudge", {"message": "Small steps still count.", "local_date": "2026-10-07"})
    assert (c.title, c.body, c.deep_link, c.tag) == (
        "A thought for today",
        "Small steps still count.",
        "/app",
        "nudge:2026-10-07",
    )


def test_daily_nudge_copy_adds_the_attribution_and_never_overflows_the_body_column():
    c = build_copy("daily_nudge", {"message": "Keep going.", "attribution": "A. Teacher", "local_date": "d"})
    assert c.body == "Keep going. (A. Teacher)"
    long = build_copy("daily_nudge", {"message": "x" * 400, "local_date": "d"})
    assert len(long.body) == 240 and long.body.endswith("…")
