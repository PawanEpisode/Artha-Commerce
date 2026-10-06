from django.apps import AppConfig


def _webpush_channel():
    from .channels.webpush import WebPushChannel  # imported on first send, not at start-up

    return WebPushChannel()


class NotificationsConfig(AppConfig):
    name = "modules.notifications"
    label = "notifications"

    def ready(self):
        from core import registry

        from . import channels, handlers, subscribers
        from .selectors import export
        from .services import erasure

        registry.register_eraser("notifications", erasure.delete_all_for_user)
        registry.register_exporter("notifications", export.export_all)
        channels.register_channel(channels.PUSH, _webpush_channel)
        handlers.register_defaults()
        subscribers.register()  # idempotent: ready() may run twice
