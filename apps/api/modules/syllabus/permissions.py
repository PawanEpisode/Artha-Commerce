from rest_framework.permissions import BasePermission

from modules.profiles.models import Profile
from modules.profiles.selectors import get_profile


class IsSyllabusEditor(BasePermission):
    """Taxonomy writes need the `editor` or `admin` role on the student's profile (checked against the database)."""

    message = "Editor or admin role required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        profile = get_profile(user.id)
        return bool(profile and profile.role in {Profile.Role.EDITOR, Profile.Role.ADMIN})
