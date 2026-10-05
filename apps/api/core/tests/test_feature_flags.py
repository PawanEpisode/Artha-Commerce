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
    assert "treating it as on" in caplog.text


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


def test_failures_are_not_cached_so_the_next_request_tries_again(posthog):
    posthog.result = TimeoutError("down")
    feature_flags.flag_enabled("syllabus_coverage", "u1")
    posthog.result = False
    assert feature_flags.flag_enabled("syllabus_coverage", "u1") is False
