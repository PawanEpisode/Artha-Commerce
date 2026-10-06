import json
from datetime import UTC, datetime, timedelta

import pytest

from modules.notifications.domain.catalogue import get_event
from modules.notifications.domain.dedupe import normalize_parts, placeholders
from modules.notifications.domain.deeplinks import InvalidDeepLink
from modules.notifications.domain.devices import InvalidKeys, derive_label, validate_keys
from modules.notifications.domain.payload import (
    MAX_PAYLOAD_BYTES,
    PayloadAction,
    PayloadTooLarge,
    build_payload,
    delivery_window,
    encode_payload,
    link_with_notification,
)
from modules.notifications.tests.helpers import make_keys

NOW = datetime(2026, 10, 5, 4, 30, tzinfo=UTC)


# --- labels and keys ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "platform, browser, mode, expected",
    [
        ("android", "chrome", "browser", "Chrome on Android"),
        ("macos", "safari", "browser", "Safari on Mac"),
        ("ios", "safari", "standalone", "Safari on iOS (installed app)"),
        ("windows", "edge", "browser", "Edge on Windows"),
        ("linux", "firefox", "browser", "Firefox on Linux"),
        ("other", "chrome", "browser", "Chrome"),
        ("android", "other", "browser", "Browser on Android"),
        ("other", "other", "browser", "Browser"),
        ("other", "other", "app", "Browser (installed app)"),
    ],
)
def test_label(platform, browser, mode, expected):
    assert derive_label(platform, browser, mode) == expected


def test_valid_keys_pass():
    keys = make_keys()
    validate_keys(keys["p256dh"], keys["auth"])


@pytest.mark.parametrize(
    "p256dh, auth",
    [
        ("", "x"),
        ("not base64 !!", "AAAAAAAAAAAAAAAAAAAAAA"),
        ("AAAA", "AAAAAAAAAAAAAAAAAAAAAA"),  # too short
        (None, "AAAAAAAAAAAAAAAAAAAAAA"),
        ("A" * 400, "AAAAAAAAAAAAAAAAAAAAAA"),
    ],
)
def test_bad_public_key(p256dh, auth):
    with pytest.raises(InvalidKeys):
        validate_keys(p256dh, auth)


def test_bad_auth_secret_and_wrong_point_prefix():
    keys = make_keys()
    with pytest.raises(InvalidKeys):
        validate_keys(keys["p256dh"], "AAAA")
    with pytest.raises(InvalidKeys):  # 65 bytes but not an uncompressed point (first byte is not 0x04)
        validate_keys("A" * 87, keys["auth"])


# --- payload -----------------------------------------------------------------------------------------------------


def test_payload_v1_shape_matches_the_prd():
    payload = build_payload(
        notification_id="n-1",
        category="timer",
        title="Round 2 done",
        body="25 minutes on GST.",
        tag="timer:abc",
        deep_link="/app/focus",
        actions=[PayloadAction("break", "Start break")],
    )
    assert payload == {
        "v": 1,
        "id": "n-1",
        "category": "timer",
        "title": "Round 2 done",
        "body": "25 minutes on GST.",
        "tag": "timer:abc",
        "url": "/app/focus?n=n-1",
        "actions": [{"id": "break", "title": "Start break"}],
    }


def test_actions_default_to_empty_list():
    payload = build_payload(notification_id="n", category="timer", title="t", body="b", tag="x", deep_link="/app/focus")
    assert payload["actions"] == []


@pytest.mark.parametrize(
    "link, expected",
    [
        ("/app/focus", "/app/focus?n=1"),
        ("/app/focus?tab=a", "/app/focus?tab=a&n=1"),
        ("/app/focus?n=old", "/app/focus?n=1"),
        ("/app/focus#top", "/app/focus?n=1#top"),
        ("/app", "/app?n=1"),
    ],
)
def test_link_gets_the_notification_marker(link, expected):
    assert link_with_notification(link, 1) == expected


@pytest.mark.parametrize("link", ["//evil.example", "https://evil.example/app", "/admin", "/app/../admin", ""])
def test_payload_refuses_unsafe_links(link):
    with pytest.raises(InvalidDeepLink):
        link_with_notification(link, 1)


def test_encoding_is_compact_utf8_and_round_trips():
    payload = build_payload(
        notification_id="n", category="timer", title="Round 2 done", body="शाबाश", tag="t", deep_link="/app/focus"
    )
    text = encode_payload(payload)
    assert " " not in text.replace("Round 2 done", "")
    assert json.loads(text) == payload and "शाबाश" in text


def test_payload_over_three_kb_is_refused():
    payload = build_payload(
        notification_id="n", category="c", title="t", body="x" * MAX_PAYLOAD_BYTES, tag="t", deep_link="/app/focus"
    )
    with pytest.raises(PayloadTooLarge):
        encode_payload(payload)


def test_payload_never_carries_keys():
    text = encode_payload(
        build_payload(notification_id="n", category="c", title="t", body="b", tag="t", deep_link="/app/focus")
    )
    assert not {"endpoint", "p256dh", "auth", "keys"} & set(json.loads(text))


@pytest.mark.parametrize(
    "priority, expires_in, ttl, urgency",
    [
        (0, None, 300, "high"),
        (1, None, 3600, "normal"),
        (2, None, 3600, "low"),
        (3, timedelta(hours=6), 6 * 3600, "very-low"),
        (3, timedelta(days=9), 86400, "very-low"),  # capped at a day
        (1, timedelta(seconds=-5), 1, "normal"),  # never zero or negative
    ],
)
def test_delivery_window(priority, expires_in, ttl, urgency):
    expires_at = NOW + expires_in if expires_in is not None else None
    assert delivery_window(priority, NOW, expires_at) == (ttl, urgency)


# --- dedupe references -------------------------------------------------------------------------------------------


def test_dedupe_reference_single_value_or_mapping():
    spec = get_event("evaluation_ready")
    assert placeholders(spec) == ("attempt_id",)
    assert normalize_parts(spec, "a-1") == {"attempt_id": "a-1"}
    assert normalize_parts(spec, {"attempt_id": "a-2"}) == {"attempt_id": "a-2"}


def test_dedupe_reference_needs_a_mapping_for_multi_part_templates():
    spec = get_event("timer_end")
    assert placeholders(spec) == ("client_id", "version")
    with pytest.raises(ValueError):
        normalize_parts(spec, "only-one")


# --- declarative push (FR-N35) -----------------------------------------------------------------------------------


def test_declarative_fields_sit_beside_the_worker_fields():
    from modules.notifications.domain.payload import DECLARATIVE_MAGIC, with_declarative_fields

    base = build_payload(
        notification_id="n1",
        category="timer",
        title="Round 2 done",
        body="25 min",
        tag="timer:a",
        deep_link="/app/focus",
    )
    out = with_declarative_fields(base, web_origin="https://app.example.com/")
    assert out["web_push"] == DECLARATIVE_MAGIC == 8030
    assert out["notification"] == {
        "title": "Round 2 done",
        "body": "25 min",
        "navigate": "https://app.example.com/app/focus?n=n1",
        "silent": False,
    }
    assert {k: out[k] for k in base} == base  # the worker's own fields are untouched
    assert len(encode_payload(out).encode()) < MAX_PAYLOAD_BYTES


@pytest.mark.parametrize("origin", ["", "http://app.example.com", "app.example.com"])
def test_declarative_fields_need_an_https_origin(origin):
    from modules.notifications.domain.payload import with_declarative_fields

    base = build_payload(notification_id="n1", category="c", title="t", body="b", tag="x", deep_link="/app/focus")
    with pytest.raises(ValueError):
        with_declarative_fields(base, web_origin=origin)
