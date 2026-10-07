"""Pure rules of the timer alert buttons (W3.6, FR-N12)."""

import pytest

from modules.notifications.domain import actions
from modules.notifications.domain.enums import ButtonAction
from modules.notifications.domain.payload import PayloadAction, build_payload, encode_payload

START_BREAK, PAUSE, START_FOCUS = ButtonAction.START_BREAK, ButtonAction.PAUSE, ButtonAction.START_FOCUS


@pytest.mark.parametrize(
    "event, context, expected",
    [
        ("timer_end", {"overtime": True}, (START_BREAK, PAUSE)),
        ("timer_end", {"overtime": False, "break_starts_itself": False}, (START_BREAK,)),
        ("timer_end", {"overtime": False, "break_starts_itself": True}, ()),
        ("timer_end", {"overtime": True, "away": True}, ()),
        ("break_over", {"next_round": 2}, (START_FOCUS,)),
        ("break_over", {"away": True}, ()),
        ("daily_nudge", {}, ()),
        ("goal_reached", {"overtime": True}, ()),
    ],
)
def test_which_buttons_an_alert_carries(event, context, expected):
    assert actions.buttons_for(event, context) == expected


def test_titles_are_short_and_name_the_next_round():
    assert actions.button_title(START_BREAK) == "Start break"
    assert actions.button_title(PAUSE) == "Pause"
    assert actions.button_title(ButtonAction.RESUME) == "Resume"
    assert actions.button_title(START_FOCUS, {"next_round": 3}) == "Start round 3"
    assert actions.button_title(START_FOCUS, {}) == "Start next round"


def test_only_android_gets_buttons():
    assert actions.PLATFORMS == frozenset({"android"})


def test_token_shape_and_hash():
    token = "A" * 43
    assert actions.well_formed(token) and actions.well_formed("a-b_" + "c" * 39)
    for bad in ("", "A" * 42, "A" * 44, "A" * 42 + "=", "A" * 42 + "/", None, 42):
        assert not actions.well_formed(bad)
    digest = actions.hash_token(token)
    assert len(digest) == 64 and digest == actions.hash_token(token) and digest != actions.hash_token("B" * 43)


def test_ttl_is_ten_minutes():
    assert actions.TOKEN_TTL.total_seconds() == 600


@pytest.mark.parametrize("action", list(ButtonAction))
def test_every_action_has_words_for_every_outcome(action):
    for outcome in ("done", "already", "stale", "needs_app"):
        copy = actions.confirmation(action, outcome)
        assert copy.title and copy.body and len(copy.title) <= 40
    assert actions.confirmation(action, "stale") == actions.STALE
    assert actions.confirmation(action, "needs_app") == actions.NEEDS_APP


def test_a_payload_with_two_buttons_stays_well_inside_the_push_limit():
    payload = build_payload(
        notification_id="0d8f7a7e-8d0e-4c43-9a6f-11c8b7b0a001",
        category="timer",
        title="Round target reached",
        body="x" * 240,
        tag="timer:0d8f7a7e-8d0e-4c43-9a6f-11c8b7b0a001",
        deep_link="/app/focus",
        actions=(PayloadAction("start_break", "Start break", "T" * 43), PayloadAction("pause", "Pause", "U" * 43)),
    )
    assert payload["actions"][0] == {"id": "start_break", "title": "Start break", "token": "T" * 43}
    assert len(encode_payload(payload).encode()) < 1024


def test_buttons_without_a_token_keep_the_old_shape():
    payload = build_payload(
        notification_id="n",
        category="timer",
        title="t",
        body="b",
        tag="g",
        deep_link="/app",
        actions=(PayloadAction("x", "X"),),
    )
    assert payload["actions"] == [{"id": "x", "title": "X"}]
