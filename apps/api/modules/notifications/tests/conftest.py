import pytest


@pytest.fixture(autouse=True)
def _notifications_on(settings, monkeypatch):
    """Environment switch on and PostHog answering `on`, so tests exercise the feature itself."""
    settings.NOTIFICATIONS_ENABLED = True
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: True)
