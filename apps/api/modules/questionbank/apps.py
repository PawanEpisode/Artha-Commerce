from django.apps import AppConfig


class QuestionbankConfig(AppConfig):
    name = "modules.questionbank"
    label = "questionbank"

    def ready(self) -> None:
        from core import registry as account_registry

        from . import registry  # noqa: F401
        from .services import delete_all_for_user, export_for_user

        account_registry.register_eraser("questionbank", delete_all_for_user)
        account_registry.register_exporter("questionbank", export_for_user)
