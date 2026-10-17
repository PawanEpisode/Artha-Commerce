"""
Django AppConfig for Performance Analytics (F-10).
"""

from __future__ import annotations

from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "modules.analytics"
    label = "analytics"
    verbose_name = "Performance Analytics"

    def ready(self) -> None:
        from core import registry as account_registry

        from .pickers import register_analytics_origins
        from .services import delete_all_for_user, export_for_user
        from .subscribers import register_subscribers

        register_analytics_origins()
        register_subscribers()

        # DPDP Account Erasure & Export registration
        account_registry.register_eraser("analytics", delete_all_for_user)
        account_registry.register_exporter("analytics", export_for_user)
