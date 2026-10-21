"""
Django AppConfig for Mock Tests module.
"""

from __future__ import annotations

from django.apps import AppConfig


class MocktestConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.mocktest"
    label = "mocktest"
    verbose_name = "Mock Tests and MTP"

    def ready(self) -> None:
        from .registry import register_mocktest_origins_and_pickers

        register_mocktest_origins_and_pickers()
