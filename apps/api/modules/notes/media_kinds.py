"""
The attachment kinds notes stores (F-03 ERD 3.3), registered with `media` at app start. Quota stays here: the kind's
`reserve` and `release` call the atomic statements in `services.quota`, so `media` never learns what a plan is.

R1 registers `note_image` only. R2 adds `note_pdf` (and `note_export`) next to it with a ClamAV scan.
"""

from __future__ import annotations

import uuid

from modules.media.registry import KindSpec

from .services import quota

BUCKET = "notes-private"
NOTE_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp"})
NOTE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
_EXTENSION = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _image_path(user_id: str, attachment_id: uuid.UUID, mime: str) -> str:
    """`{user}/notes/images/{attachment}.{ext}`: ids only, never a file name or a note title."""
    return f"{user_id}/notes/images/{attachment_id}.{_EXTENSION[mime]}"


NOTE_IMAGE = KindSpec(
    name="note_image",
    bucket=BUCKET,
    mimes=NOTE_IMAGE_MIMES,
    max_bytes=lambda user_id: NOTE_IMAGE_MAX_BYTES,
    reserve=quota.reserve_bytes,
    release=quota.release_bytes,
    path_for=_image_path,
    scan="none",  # R1: images are trusted at completion; R2's worker adds re-encode and scan before `clean`
    flag="notes",
)
