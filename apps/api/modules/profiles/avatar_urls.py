"""
The only place that turns an avatar key into a URL (ERD 0.6). Moving from the public bucket to signed URLs later is a
one-file change: this function. A preset is not a URL at all (the web draws it from the design system by key).
"""

from __future__ import annotations

from django.conf import settings

from core.storage import public_url

from .models import Profile


def avatar_urls(profile: Profile) -> dict | None:
    if profile.avatar_kind != Profile.AvatarKind.UPLOAD:
        return None
    bucket = settings.SUPABASE_AVATAR_BUCKET
    stem = profile.avatar_key
    return {"small": public_url(bucket, f"{stem}-128.webp"), "large": public_url(bucket, f"{stem}-512.webp")}


def avatar_summary(profile: Profile) -> dict:
    """What the web renders: kind, preset key, version (part of its query key) and the two rendition URLs."""
    return {
        "kind": profile.avatar_kind,
        "preset_key": profile.avatar_preset_key or None,
        "version": profile.avatar_version,
        "urls": avatar_urls(profile),
    }
