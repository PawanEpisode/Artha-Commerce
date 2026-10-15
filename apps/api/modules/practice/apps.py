"""
Django AppConfig for the Practice Engine module.
"""

from django.apps import AppConfig


class PracticeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.practice"
    label = "practice"
    verbose_name = "Practice Engine"

    def ready(self):
        from core import registry as account_registry

        from . import services

        account_registry.register_eraser("practice", services.delete_all_for_user)
        account_registry.register_exporter("practice", services.export_for_user)

        from .pickers.builtin import register_builtin_pickers
        from .registry import OriginSpec, register_origin

        register_builtin_pickers()
        register_origin(
            "questionbank",
            OriginSpec(
                allowed_modes={"untimed", "timed", "chapter_quiz", "revision", "custom_test", "exam"},
                default_feedback_policy="at_end",
            ),
        )

        from .ports import register_ports
        from .subscribers import register_subscribers

        register_ports()
        register_subscribers()
