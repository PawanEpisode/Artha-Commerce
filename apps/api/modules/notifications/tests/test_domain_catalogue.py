import pytest

from modules.notifications.domain.catalogue import (
    CATEGORIES,
    EVENTS,
    SYSTEM_EVENTS,
    UnknownEvent,
    UnknownSwitch,
    get_event,
    is_default_enabled,
    is_enabled,
    validate_switch,
)
from modules.notifications.domain.copy import _BUILDERS
from modules.notifications.domain.dedupe import build_dedupe_key


def test_every_event_belongs_to_a_known_category():
    keys = {spec.key for spec in CATEGORIES}
    assert all(event.category in keys for event in EVENTS.values())


def test_only_timer_events_are_exempt():
    assert {key for key, spec in EVENTS.items() if spec.exempt} == {"timer_end", "break_over"}


def test_event_keys_fit_the_database_column():
    assert all(len(key) <= 24 for key in EVENTS)


def test_copy_builders_exist_only_for_catalogued_events():
    assert set(_BUILDERS) <= set(EVENTS) | set(SYSTEM_EVENTS)


def test_defaults_progress_is_email_and_inbox_the_rest_push_and_inbox():
    assert is_default_enabled("progress", "email") and not is_default_enabled("progress", "push")
    assert is_default_enabled("timer", "push") and not is_default_enabled("timer", "email")
    assert all(is_default_enabled(spec.key, "inbox") for spec in CATEGORIES)


def test_override_wins_over_default():
    assert not is_enabled("timer", "push", {("timer", "push"): False})
    assert is_enabled("timer", "push", {("tracker", "push"): False})


def test_validate_switch_rejects_unknown_pairs():
    assert validate_switch("timer", "push")
    with pytest.raises(UnknownSwitch):
        validate_switch("nope", "push")
    with pytest.raises(UnknownSwitch):
        validate_switch("timer", "sms")


def test_get_event_unknown():
    with pytest.raises(UnknownEvent):
        get_event("nope")


def test_dedupe_key_is_stable_and_checked():
    spec = get_event("timer_end")
    assert build_dedupe_key(spec, client_id="abc", version=3) == "timer_end:abc:3"
    with pytest.raises(ValueError):
        build_dedupe_key(spec, client_id="abc")
    with pytest.raises(ValueError):
        build_dedupe_key(spec, client_id="x" * 200, version=1)


def test_break_over_shares_the_round_key_so_the_pair_never_double_fires():
    assert get_event("break_over").dedupe_template == get_event("timer_end").dedupe_template


def test_system_events_are_exempt_unique_and_not_switchable():
    spec = get_event("test_push")
    assert spec.system and spec.exempt and spec.key not in EVENTS
    assert all(len(key) <= 24 for key in SYSTEM_EVENTS)
    assert build_dedupe_key(spec, nonce="a") != build_dedupe_key(spec, nonce="b")
    assert "system" not in {c.key.value for c in CATEGORIES}
    with pytest.raises(UnknownSwitch):
        validate_switch("system", "push")
