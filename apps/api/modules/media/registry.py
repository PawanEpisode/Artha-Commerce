"""
Attachment kinds (F-06 ERD 3.3, F-03 ERD 3.3). A feature registers what it stores once, at app start, and `media` stays
generic: it validates type and size, calls the kind's own quota hooks and talks to storage. Open for extension, closed for
modification: adding the PDF kind in a later release is one `register_kind` call in the notes app.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

DEFAULT_RESERVATION_MINUTES = 30
DEFAULT_READ_URL_SECONDS = 3600


@dataclass(frozen=True)
class KindSpec:
    """
    name           registry key, stored on the row
    bucket         Supabase Storage bucket (private)
    mimes          the only content types accepted
    max_bytes      `fn(user_id) -> int`, so a plan can change the limit
    reserve        `fn(user_id, bytes)` takes quota atomically and raises (429 `quota_exceeded`) when there is none
    release        `fn(user_id, bytes)` gives it back; must tolerate a student whose usage row is already gone
    path_for       `fn(user_id, attachment_id, mime) -> object path` (ids only: no file names in paths)
    on_clean       `fn(attachment_id)` once the file may be used (for example to queue inspection)
    on_reject      `fn(attachment_id, reason)` after a file was rejected (wrong content, malware, more bytes than declared)
    sniff          `fn(first_bytes) -> reason | None`: a content check at completion, on the first `sniff_bytes` of the object
    scan           "clamav" (a `media.scan` job scans before `clean`; with the null scanner it is `clean` at completion) or
                   "none" (trusted by construction, `clean` at completion)
    flag           optional feature flag that must be on for the student to upload this kind
    public         False for kinds the browser may not start through `/media/uploads/`: a module's own service creates them
                   (documents reserve quota together with a row; exports are built by the worker)
    retention_days how long the owning module keeps a finished object (exports: 7); the owner sets its expiry and purges it
    """

    name: str
    bucket: str
    mimes: frozenset[str]
    max_bytes: Callable[[str], int]
    reserve: Callable[[str, int], None]
    release: Callable[[str, int], None]
    path_for: Callable[[str, uuid.UUID, str], str]
    on_clean: Callable[[uuid.UUID], None] | None = None
    on_reject: Callable[[uuid.UUID, str], None] | None = None
    sniff: Callable[[bytes], str | None] | None = None
    sniff_bytes: int = 1024
    scan: str = "clamav"
    flag: str | None = None
    public: bool = True
    retention_days: int | None = None
    read_url_seconds: int = DEFAULT_READ_URL_SECONDS
    reservation_minutes: int = DEFAULT_RESERVATION_MINUTES


class UnknownKind(KeyError):
    pass


_kinds: dict[str, KindSpec] = {}


def register_kind(spec: KindSpec) -> None:
    """Idempotent for the same spec (an app's `ready()` can run twice); a different spec under one name is a bug."""
    existing = _kinds.get(spec.name)
    if existing is not None and existing != spec:
        raise ValueError(f"Attachment kind {spec.name!r} is already registered with a different spec.")
    _kinds[spec.name] = spec


def get_kind(name: str) -> KindSpec:
    try:
        return _kinds[name]
    except KeyError:
        raise UnknownKind(name) from None


def kind_names() -> list[str]:
    return sorted(_kinds)


def public_kind_names() -> list[str]:
    """The kinds a student may start through the generic upload endpoint."""
    return sorted(name for name, spec in _kinds.items() if spec.public)
