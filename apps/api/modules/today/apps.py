from django.apps import AppConfig


class TodayConfig(AppConfig):
    name = "modules.today"
    label = "today"

    # Providers register themselves from their own `AppConfig.ready()` (see `registry.py`); Today imports no provider code.
    # The completion subscribers, the account eraser and exporter, and the tick job are wired here in later waves (W3, W6).
