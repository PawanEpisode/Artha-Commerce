"""
Permission classes for F-11 Paper Analysis and Recommendations.
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from core.permissions import flag_required
from modules.profiles.models import Profile
from modules.profiles.selectors import get_profile

# Fail-closed feature flag permissions
PaperAnalysisFlag = flag_required("paper_analysis", strict=True)
PaperAnalysisPlannerFlag = flag_required("paper_analysis_planner", strict=True)


class IsEditor(BasePermission):
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
    message = "Admin role required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if getattr(user, "is_superuser", False):
            return True
        profile = get_profile(user.id)
        return bool(profile and profile.role == Profile.Role.ADMIN)
