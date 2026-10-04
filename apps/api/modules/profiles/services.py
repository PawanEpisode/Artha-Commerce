"""Write operations and business rules. Views call these; they never touch the ORM directly."""

from typing import Any

from core.authentication import SupabaseUser

from .models import Profile
from .selectors import get_profile


def get_or_create_profile(user: SupabaseUser) -> Profile:
    """Profiles are created lazily on the first authenticated request, seeded from the JWT claims."""
    existing = get_profile(user.id)
    if existing:
        return existing
    meta = user.claims.get("user_metadata", {}) or {}
    profile, _ = Profile.objects.get_or_create(
        pk=user.id,
        defaults={
            "email": user.email,
            "full_name": meta.get("full_name") or meta.get("name") or "",
            "avatar_url": meta.get("avatar_url") or meta.get("picture") or "",
        },
    )
    return profile


def update_profile(profile: Profile, data: dict[str, Any]) -> Profile:
    for field, value in data.items():
        setattr(profile, field, value)
    profile.save(update_fields=[*data.keys(), "updated_at"])
    return profile
