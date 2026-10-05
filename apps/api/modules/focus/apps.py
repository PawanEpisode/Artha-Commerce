from django.apps import AppConfig


class FocusConfig(AppConfig):
    name = "modules.focus"
    label = "focus"

    def ready(self):
        from core import registry
        from modules.tracking import services as tracking

        from . import selectors, services

        # Dependency direction is focus -> tracking: Pomodoro tells the tracker when it is running so only one live timer
        # exists. Tracking never imports this module.
        tracking.register_live_timer_provider(selectors.live_kind)

        registry.register_eraser("focus", services.delete_all_for_user)
        registry.register_exporter("focus", selectors.export_all)
