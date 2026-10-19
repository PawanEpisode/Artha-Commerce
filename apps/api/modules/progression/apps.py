from django.apps import AppConfig


class ProgressionConfig(AppConfig):
    name = "modules.progression"
    label = "progression"

    def ready(self):
        from core import registry

        from . import selectors, services

        registry.register_eraser("progression", services.delete_all_for_user)
        registry.register_exporter("progression", selectors.export_all)
