import logging

import pytest

from core import feature_flags


class FakePostHog:
    """Stands in for the PostHog client: records calls, returns what the test sets."""

    def __init__(self, result=True):
        self.result = result
        self.calls: list[tuple[str, str, dict]] = []

    def get_feature_flag(self, key, distinct_id, **kwargs):
        self.calls.append((key, distinct_id, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def posthog(settings, monkeypatch):
    settings.POSTHOG_API_KEY = "phc_test"
    settings.FEATURE_FLAG_CACHE_SECONDS = 60
    fake = FakePostHog()
    monkeypatch.setattr(feature_flags, "_client", fake)
    feature_flags.clear_flag_cache()
    yield fake
    feature_flags.clear_flag_cache()


def test_without_a_posthog_key_every_flag_is_on(settings, monkeypatch):
    settings.POSTHOG_API_KEY = ""
    monkeypatch.setattr(feature_flags, "_client", None)
    assert feature_flags.flag_enabled("anything", "user-1") is True


def test_only_an_explicit_false_turns_a_flag_off(posthog):
    posthog.result = False
    assert feature_flags.flag_enabled("syllabus_coverage", "u1") is False
    for value in (True, "variant-a", None):  # None: the flag does not exist or could not be evaluated
        feature_flags.clear_flag_cache()
        posthog.result = value
        assert feature_flags.flag_enabled("syllabus_coverage", "u1") is True


def test_a_posthog_failure_means_on_and_is_logged(posthog, caplog):
    posthog.result = TimeoutError("posthog is slow")
    with caplog.at_level(logging.WARNING, logger="core.feature_flags"):
        assert feature_flags.flag_enabled("syllabus_coverage", "u1") is True
    assert "treating it as unknown" in caplog.text


def test_a_failed_lookup_is_cached_briefly_so_an_outage_costs_one_call(posthog, monkeypatch):
    posthog.result = TimeoutError("posthog is down")
    for _ in range(5):
        assert feature_flags.flag_enabled("recall_system", "u1", strict=True) is False  # fail closed
    assert len(posthog.calls) == 1
    # ... and only briefly: after the error window the next request asks again
    monkeypatch.setattr(feature_flags.time, "monotonic", lambda: 10_000_000.0)
    posthog.result = True
    assert feature_flags.flag_enabled("recall_system", "u1", strict=True) is True
    assert len(posthog.calls) == 2


def test_the_student_id_is_the_distinct_id_and_flag_events_are_not_sent(posthog):
    feature_flags.flag_enabled("syllabus_coverage", "3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
    assert posthog.calls == [
        ("syllabus_coverage", "3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11", {"send_feature_flag_events": False})
    ]


def test_answers_are_cached_per_student_and_flag(posthog, settings):
    assert feature_flags.flag_enabled("syllabus_coverage", "u1") is True
    assert feature_flags.flag_enabled("syllabus_coverage", "u1") is True
    assert len(posthog.calls) == 1
    feature_flags.flag_enabled("syllabus_coverage", "u2")
    feature_flags.flag_enabled("other_flag", "u1")
    assert len(posthog.calls) == 3
    settings.FEATURE_FLAG_CACHE_SECONDS = 0  # expired immediately
    feature_flags.flag_enabled("syllabus_coverage", "u1")
    assert len(posthog.calls) == 4


def test_a_failure_is_retried_once_the_short_error_window_has_passed(posthog, monkeypatch):
    posthog.result = TimeoutError("down")
    feature_flags.flag_enabled("syllabus_coverage", "u1")
    posthog.result = False
    monkeypatch.setattr(feature_flags.time, "monotonic", lambda: 10_000_000.0)
    assert feature_flags.flag_enabled("syllabus_coverage", "u1") is False


def test_strict_mode_fails_closed_when_posthog_cannot_answer(posthog, settings, monkeypatch, caplog):
    posthog.result = TimeoutError("down")
    assert feature_flags.flag_enabled("push_notifications", "u1") is True  # default stays fail open
    assert feature_flags.flag_enabled("push_notifications", "u1", strict=True) is False

    feature_flags.clear_flag_cache()
    posthog.result = None  # unknown flag
    assert feature_flags.flag_enabled("push_notifications", "u1") is True
    assert feature_flags.flag_enabled("push_notifications", "u1", strict=True) is False

    settings.POSTHOG_API_KEY = ""
    monkeypatch.setattr(feature_flags, "_client", None)
    assert feature_flags.flag_enabled("push_notifications", "u1") is True
    assert feature_flags.flag_enabled("push_notifications", "u1", strict=True) is False


def test_strict_mode_needs_an_explicit_on_and_respects_an_explicit_off(posthog):
    posthog.result = True
    assert feature_flags.flag_enabled("push_notifications", "u1", strict=True) is True
    feature_flags.clear_flag_cache()
    posthog.result = "variant-a"
    assert feature_flags.flag_enabled("push_notifications", "u1", strict=True) is True
    feature_flags.clear_flag_cache()
    posthog.result = False
    assert feature_flags.flag_enabled("push_notifications", "u1", strict=True) is False
    assert feature_flags.flag_enabled("push_notifications", "u1") is False
