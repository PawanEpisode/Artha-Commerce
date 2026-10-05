"""Writes for identity: lazy profile creation and the name."""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from core import events
from core.authentication import SupabaseUser

from ..domain.names import normalize_name
from ..models import Onboarding, Profile
from ..selectors import get_profile


def get_or_create_profile(user: SupabaseUser) -> Profile:
    """
    Profiles are created lazily on the first authenticated request. The name is NOT copied from the provider: the
    student confirms it in onboarding (the suggestion is served separately), so "has a name" always means they chose it.
    The provider photo URL is kept only as the source for the optional "Use my Google photo" action.
    """
    existing = get_profile(user.id)
    if existing:
        return existing
    meta = user.claims.get("user_metadata", {}) or {}
    profile, _ = Profile.objects.get_or_create(
        pk=user.id,
        defaults={"email": user.email, "avatar_url": meta.get("avatar_url") or meta.get("picture") or ""},
    )
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
