"""
Question bank permissions (F-06 ERD 7).
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from modules.profiles.models import Profile
from modules.profiles.selectors import get_profile


class IsEditor(BasePermission):
    """Requires editor or admin role on the user profile."""

    message = "Editor or admin role required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_staff", False):
            return True
        profile = get_profile(user.id)
        return bool(profile and profile.role in {Profile.Role.EDITOR, Profile.Role.ADMIN})


class IsAdmin(BasePermission):
    """Requires admin role on the user profile."""

    message = "Admin role required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True
        profile = get_profile(user.id)
        return bool(profile and profile.role == Profile.Role.ADMIN)
