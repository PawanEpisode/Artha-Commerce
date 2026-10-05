from django.apps import AppConfig


class TrackingConfig(AppConfig):
    name = "modules.tracking"
    label = "tracking"

    def ready(self):
        from core import registry

        from . import selectors, services

        registry.register_eraser("tracking", services.delete_all_for_user)
        registry.register_exporter("tracking", selectors.export_all)
