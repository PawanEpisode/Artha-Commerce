"""
Django AppConfig for PYQ module.
"""

from __future__ import annotations

from django.apps import AppConfig


class PyqConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.pyq"
    label = "pyq"
    verbose_name = "Previous Year Questions"

    def ready(self) -> None:
        from .pickers import register_pyq_pickers_and_origins

        register_pyq_pickers_and_origins()
