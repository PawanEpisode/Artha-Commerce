from django.apps import AppConfig


class NotesConfig(AppConfig):
    name = "modules.notes"
    label = "notes"

    def ready(self):
        from core import jobs, registry
        from modules.media import registry as media_registry

        from . import jobs as notes_jobs
        from . import selectors, services
        from .media_kinds import NOTE_EXPORT, NOTE_IMAGE, NOTE_PDF

        for kind in (NOTE_IMAGE, NOTE_PDF, NOTE_EXPORT):
            media_registry.register_kind(kind)
        notes_jobs.register_handlers(jobs)
        registry.register_eraser("notes", services.account.delete_all_for_user)
        registry.register_exporter("notes", selectors.export_all)
