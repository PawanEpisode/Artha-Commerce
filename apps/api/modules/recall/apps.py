from django.apps import AppConfig


class RecallConfig(AppConfig):
    name = "modules.recall"
    label = "recall"

    def ready(self) -> None:
        # The kind registry fills itself on import; the provider makes Notes' "Make a card" work (flag aware, see provider.py).
        # Erasers and exporters are registered here in W11.
        from core.recall_port import register_recall_provider

        from . import registry  # noqa: F401
        from .provider import RecallProviderImpl

        register_recall_provider(RecallProviderImpl())
