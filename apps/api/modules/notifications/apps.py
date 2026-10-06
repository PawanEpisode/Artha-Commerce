from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "modules.notifications"
    label = "notifications"

    def ready(self):
        from core import registry

        from .selectors import export
        from .services import erasure

        registry.register_eraser("notifications", erasure.delete_all_for_user)
        registry.register_exporter("notifications", export.export_all)
