"""Writes for the profile picture: preset, remove, upload. Files are only ever touched through `core.storage`."""

from __future__ import annotations

import logging
import secrets

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core import events
from core import storage as storage_module
from core.storage import StorageError

from ..domain import avatars
from ..domain.images import ImageRejected, process_avatar
from ..errors import ImageTooLarge, ImageTooSmall, InvalidImage, StorageUnavailable, UnknownPreset
from ..models import Profile, StorageDelete

logger = logging.getLogger(__name__)

CACHE_CONTROL = "public, max-age=31536000, immutable"
CONTENT_TYPE = "image/webp"
REJECTIONS = {"invalid_image": InvalidImage, "image_too_large": ImageTooLarge, "image_too_small": ImageTooSmall}


def _bucket() -> str:
    return settings.SUPABASE_AVATAR_BUCKET


def _paths(stem: str) -> list[str]:
    return [f"{stem}-512.webp", f"{stem}-128.webp"]


def _remove_files(user_id, paths: list[str]) -> None:
    """Delete now; whatever fails is queued for the daily sweep, so a storage outage never fails the student's request."""
    if not paths:
        return
    try:
        storage_module.get_storage().delete(_bucket(), paths)
    except Exception:
        logger.warning("Avatar files could not be deleted; queued for the sweep", exc_info=True)
        for path in paths:
            StorageDelete.objects.get_or_create(user_id=user_id, bucket=_bucket(), path=path)


def _change(user_id, *, kind: str, preset_key: str = "", stem: str = "") -> tuple[Profile, str]:
    """One atomic pointer change. Returns the profile and the previous upload stem ('' when there was none)."""
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(pk=user_id)
        previous = profile.avatar_key if profile.avatar_kind == Profile.AvatarKind.UPLOAD else ""
        profile.avatar_kind = kind
        profile.avatar_preset_key = preset_key
        profile.avatar_key = stem
        profile.avatar_version += 1
        profile.avatar_updated_at = timezone.now()
        profile.save(
            update_fields=[
                "avatar_kind",
                "avatar_preset_key",
                "avatar_key",
                "avatar_version",
                "avatar_updated_at",
                "updated_at",
            ]
        )
        transaction.on_commit(lambda: events.emit("avatar_changed", user_id=str(user_id), kind=kind))
    return profile, previous


def set_preset(user_id, key: str) -> Profile:
    if not avatars.is_preset_key(key):
        raise UnknownPreset
    profile, previous = _change(user_id, kind=Profile.AvatarKind.PRESET, preset_key=key)
    _remove_files(user_id, _paths(previous) if previous else [])
    return profile


def remove_avatar(user_id) -> Profile:
    profile, previous = _change(user_id, kind=Profile.AvatarKind.INITIALS)
    _remove_files(user_id, _paths(previous) if previous else [])
    return profile


def set_upload(user_id, data: bytes) -> Profile:
    """
    Validate and re-encode, store both renditions under a fresh random key, switch the pointer, then delete the old
    pair. Any failure after the first object is stored removes what was stored; the old avatar stays untouched.
    """
    try:
        renditions = process_avatar(data)
    except ImageRejected as exc:
        raise REJECTIONS[exc.code] from None

    stem = f"{user_id}/{secrets.token_urlsafe(16)}"
    large, small = _paths(stem)
    stored: list[str] = []
    try:
        store = storage_module.get_storage()
        for path, blob in ((large, renditions.large), (small, renditions.small)):
            store.upload(_bucket(), path, blob, content_type=CONTENT_TYPE, cache_control=CACHE_CONTROL)
            stored.append(path)
        profile, previous = _change(user_id, kind=Profile.AvatarKind.UPLOAD, stem=stem)
    except StorageError as exc:
        # The reason (no key, missing bucket, 4xx status) is for the operator's log; the student gets the generic copy.
        logger.warning("avatar upload: storage unavailable: %s", exc)
        _remove_files(user_id, stored)
        raise StorageUnavailable from None
    except Exception:
        _remove_files(user_id, stored)
        raise
    _remove_files(user_id, _paths(previous) if previous else [])
    return profile
