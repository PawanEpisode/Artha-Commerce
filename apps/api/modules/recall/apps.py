from django.apps import AppConfig


class RecallConfig(AppConfig):
    name = "modules.recall"
    label = "recall"

    def ready(self) -> None:
        # The kind registry fills itself on import; the provider makes Notes' "Make a card" work (flag aware, see provider.py).
        # Erase and export are registered with the account registry (W11, D4), so account deletion reaches recall.
        from core import jobs as core_jobs
        from core import registry as account_registry
        from core.recall_port import register_recall_provider
        from core.today_port import register_task_provider

        from . import jobs, registry, subscribers  # noqa: F401
        from .provider import RecallProviderImpl, today_tasks
        from .services import erasure

        register_recall_provider(RecallProviderImpl())
        register_task_provider("recall", today_tasks)  # F-13 Today collects it through `core.today_port` when it exists
        jobs.register_handlers(core_jobs)
        subscribers.register()
        account_registry.register_eraser("recall", erasure.delete_all_for_user)
        account_registry.register_exporter("recall", erasure.export_for_user)
