"""
Django AppConfig for MCQ Bank module.
"""

from __future__ import annotations

from django.apps import AppConfig


class McqbankConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.mcqbank"
    label = "mcqbank"
    verbose_name = "MCQ Bank"

    def ready(self) -> None:
        from .pickers import register_mcq_pickers_and_origins
        from .subscribers import register_subscribers

        register_mcq_pickers_and_origins()
        register_subscribers()
