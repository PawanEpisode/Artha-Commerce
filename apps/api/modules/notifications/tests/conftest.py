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
