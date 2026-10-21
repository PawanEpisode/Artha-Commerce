"""
Permissions and feature-flag checks for F-12 Institute Study Material.
"""

from __future__ import annotations

from rest_framework import permissions

from .errors import FeatureDisabled


def check_material_flag(request) -> None:
    """
    Checks if study_material feature flag is enabled.
    In development/testing, default is enabled.
    """
    # Feature flag check can be integrated with core/profiles or waffle
    pass


def check_material_mine_flag(request) -> None:
    """
    Checks if study_material_mine feature flag is enabled.
    """
    pass


class IsMaterialEditor(permissions.BasePermission):
    """
    Grants access to editors and admins.
    """

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser:
            return True
        role = getattr(user, "role", "")
        return role in ("editor", "admin")
