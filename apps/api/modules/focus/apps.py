from django.apps import AppConfig


class FocusConfig(AppConfig):
    name = "modules.focus"
    label = "focus"

    def ready(self):
        # Dependency direction is focus -> tracking: Pomodoro tells the tracker when it is running so only one live timer
        # exists. Tracking never imports this module.
        from modules.tracking import services as tracking

        from . import selectors

        tracking.register_live_timer_provider(selectors.live_kind)
