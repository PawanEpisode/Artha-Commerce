from django.apps import AppConfig


class CoverageConfig(AppConfig):
    name = "modules.coverage"
    label = "coverage"

    def ready(self):
        from core import events, registry

        from . import selectors, services, subscribers

        registry.register_eraser("coverage", services.delete_all_for_user)
        registry.register_exporter("coverage", selectors.export_all)
        events.subscribe(subscribers.NOTES_CHAPTER_COUNTS_CHANGED, subscribers.on_notes_chapter_counts_changed)
