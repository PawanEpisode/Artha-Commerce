from django.apps import AppConfig


class TodayConfig(AppConfig):
    name = "modules.today"
    label = "today"

    def ready(self):
        from core import registry as account_registry

        from . import analytics, completion, erasure, legacy_bridge, planner_hooks, planner_provider

        # The only provider Today itself registers: Recall's stand-in port. Real providers register from their own
        # `AppConfig.ready()` (see `registry.py`). Completion subscribers, the account eraser and exporter, and the tick job
        # are wired here in later waves (W3, W6).
        legacy_bridge.register()
        planner_provider.register()  # R2: "Read: {chapter}" for a paper behind its milestone (behind the flag `today_planner`)
        planner_hooks.install()  # reading finished, a new exam date or scheme: the plan follows
        completion.install()  # inline subscribers: owning modules' events complete tasks (PRD 5.3)
        analytics.install()  # domain events -> analytics events (schema-checked)
        account_registry.register_eraser("today", erasure.delete_all_for_user)
        account_registry.register_exporter("today", erasure.export_for_user)
