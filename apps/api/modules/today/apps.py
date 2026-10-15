from django.apps import AppConfig


class TodayConfig(AppConfig):
    name = "modules.today"
    label = "today"

    def ready(self):
        from . import completion, legacy_bridge

        # The only provider Today itself registers: Recall's stand-in port. Real providers register from their own
        # `AppConfig.ready()` (see `registry.py`). Completion subscribers, the account eraser and exporter, and the tick job
        # are wired here in later waves (W3, W6).
        legacy_bridge.register()
        completion.install()  # inline subscribers: owning modules' events complete tasks (PRD 5.3)
