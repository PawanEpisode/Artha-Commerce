from django.apps import AppConfig


class RecallConfig(AppConfig):
    name = "modules.recall"
    label = "recall"

    def ready(self) -> None:
        # The kind registry fills itself on import; the provider makes Notes' "Make a card" work (flag aware, see provider.py).
        # Erase and export are registered with the account registry (W11, D4), so account deletion reaches recall.
        from core import registry as account_registry
        from core.recall_port import register_recall_provider

        from . import registry  # noqa: F401
        from .provider import RecallProviderImpl
        from .services import erasure

        register_recall_provider(RecallProviderImpl())
        account_registry.register_eraser("recall", erasure.delete_all_for_user)
        account_registry.register_exporter("recall", erasure.export_for_user)
