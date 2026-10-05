from django.apps import AppConfig


class CoverageConfig(AppConfig):
    name = "modules.coverage"
    label = "coverage"

    def ready(self):
        from core import registry

        from . import selectors, services

        registry.register_eraser("coverage", services.delete_all_for_user)
        registry.register_exporter("coverage", selectors.export_all)
