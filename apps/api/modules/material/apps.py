"""
Django AppConfig for F-12 Institute Study Material (MAT).
"""

from __future__ import annotations

from django.apps import AppConfig


class MaterialConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.material"
    verbose_name = "Institute Study Material"

    def ready(self) -> None:
        from .registry import register_origins

        register_origins()
