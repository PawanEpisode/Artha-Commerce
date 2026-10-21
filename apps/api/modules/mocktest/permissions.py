"""
Permissions and feature flag checks for F-08 Mock Tests.
"""

from __future__ import annotations

import uuid
from rest_framework import permissions
from core import feature_flags
from .errors import FeatureDisabled


def check_mock_flag(user_id: uuid.UUID) -> None:
    """Checks mock_tests feature flag."""
    if not feature_flags.flag_enabled("mock_tests", user_id):
        raise FeatureDisabled()


def check_mock_contrib_flag(user_id: uuid.UUID) -> None:
    """Checks mock_contrib feature flag."""
    if not feature_flags.flag_enabled("mock_contrib", user_id):
        raise FeatureDisabled()


class IsMockEditor(permissions.BasePermission):
    """Allows access only to authenticated staff or editors."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return bool(request.user.is_staff or getattr(request.user, "is_editor", False))
