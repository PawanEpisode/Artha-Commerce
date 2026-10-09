"""Writes for identity: lazy profile creation and the name."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from core import events
from core.authentication import SupabaseUser
from core.feature_flags import flag_enabled

from ..domain.names import normalize_name, provider_name
from ..flags import AVATAR_FLAG
from ..models import Onboarding, Profile
from ..selectors import get_profile
from .provider_photo import import_provider_photo


def get_or_create_profile(user: SupabaseUser) -> Profile:
    """
    Profiles are created lazily on the first authenticated request. A student who signs in with Google starts with the
    name and photo Google vouches for, so the workspace greets them properly from the first screen; they can change
    either in onboarding or in Account. Email sign-ups start empty and confirm a suggestion in onboarding.
    """
    existing = get_profile(user.id)
    if existing:
        return existing
    meta = user.claims.get("user_metadata", {}) or {}
    photo = meta.get("avatar_url") or meta.get("picture") or ""
    profile, created = Profile.objects.get_or_create(
        pk=user.id,
        defaults={
            "email": user.email,
            "full_name": provider_name(user.claims),
            "avatar_url": photo if len(photo) <= 200 else "",
        },
    )
    if created and photo and flag_enabled(AVATAR_FLAG, user.id) and import_provider_photo(user.id, photo):
        profile.refresh_from_db()
    return profile


def get_or_create_onboarding(user_id) -> Onboarding:
    """Race safe: two first requests from two tabs end with one row (get_or_create plus an IntegrityError retry)."""
    try:
        row, _ = Onboarding.objects.get_or_create(pk=user_id)
    except IntegrityError:
        row = Onboarding.objects.get(pk=user_id)
    return row


def ensure_student(user: SupabaseUser) -> tuple[Profile, Onboarding]:
    return get_or_create_profile(user), get_or_create_onboarding(user.id)


@transaction.atomic
def update_name(user_id, raw_name: str) -> Profile:
    """Raises `InvalidName` (a ValueError with a student-facing message). Unchanged names do not touch the row."""
    name = normalize_name(raw_name)
    profile = Profile.objects.select_for_update().get(pk=user_id)
    if profile.full_name != name:
        profile.full_name = name
        profile.save(update_fields=["full_name", "updated_at"])
        transaction.on_commit(lambda: events.emit("profile_updated", user_id=str(user_id), fields=["full_name"]))
    return profile


def touch(profile: Profile) -> None:
    """Bump `updated_at` after a change made through another table (used by avatar changes in later slices)."""
    Profile.objects.filter(pk=profile.pk).update(updated_at=timezone.now())


class StaffRoleError(ValueError):
    """The profile for an address is missing or ambiguous, or the role is not one of the three."""


def set_staff_role(email: str, role: str) -> Profile:
    """
    Set `profiles.role` for the ONE profile with this address (ignoring case). Staff roles are never granted through the API
    (the serializers do not expose `role`); this is the operator path behind the `grant_staff_role` command. The person must
    have signed in once so the profile exists.
    """
    if role not in Profile.Role.values:
        raise StaffRoleError(f"Role must be one of: {', '.join(Profile.Role.values)}.")
    rows = list(Profile.objects.filter(email__iexact=(email or "").strip())[:2])
    if not rows:
        raise StaffRoleError(
            f"No profile with the address {email!r}. Ask the person to sign in once, then run this again."
        )
    if len(rows) > 1:
        raise StaffRoleError(f"More than one profile has the address {email!r}; fix that first.")
    profile = rows[0]
    if profile.role != role:
        profile.role = role
        profile.save(update_fields=["role", "updated_at"])
    return profile
