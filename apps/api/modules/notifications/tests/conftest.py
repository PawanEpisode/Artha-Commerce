import pytest
from cryptography.fernet import Fernet
from django.core.cache import cache

from modules.notifications import channels


@pytest.fixture(autouse=True)
def _notifications_on(settings, monkeypatch):
    """Environment switch on and PostHog answering `on`, so tests exercise the feature itself."""
    settings.NOTIFICATIONS_ENABLED = True
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: True)


@pytest.fixture(autouse=True)
def _crypto(settings):
    settings.FIELD_ENCRYPTION_KEYS = [Fernet.generate_key().decode()]
    settings.FIELD_HASH_PEPPER = "pepper-pepper-pepper"


@pytest.fixture(autouse=True)
def fake_push():
    """A recording channel for every test (FR-N31): nothing here can reach a push service."""
    fake = channels.FakeChannel()
    channels.use_channel(channels.PUSH, fake)
    yield fake
    channels.reset_channels()


@pytest.fixture(autouse=True)
def _fresh_throttle_counters():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def fake_queue(settings):
    """A recording queue for every test (FR-N31): nothing here can reach QStash. Callbacks point at a fixed origin."""
    from modules.notifications.scheduling import queue

    settings.NOTIFICATIONS_PUBLIC_BASE_URL = "https://api.example.test"
    fake = queue.NullQueue()
    queue.use_queue(fake)
    yield fake
    queue.reset_queue()


@pytest.fixture(autouse=True)
def _subscribers_registered():
    """Another test module may clear the event bus; make sure the notifications subscriber is listening."""
    from modules.notifications import handlers, subscribers

    handlers.register_defaults()
    subscribers.register()


@pytest.fixture
def bench(monkeypatch, django_capture_on_commit_callbacks):
    """A student's Pomodoro timer on a movable clock, driven through the real focus services."""
    from modules.notifications.tests.timer_bench import Bench

    return Bench(monkeypatch, django_capture_on_commit_callbacks)


@pytest.fixture
def scheme(db):
    from modules.syllabus.tests.helpers import make_scheme

    return make_scheme()
