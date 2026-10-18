"""
Paper Analysis Django application configuration.
"""

from __future__ import annotations

from django.apps import AppConfig


class PaperAnalysisConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.paperanalysis"
    verbose_name = "Paper Analysis and Recommendations"

    def ready(self) -> None:
        from . import (
            jobs,
            providers,  # noqa: F401
            signals_in,  # noqa: F401
        )
        jobs.register_handlers()
