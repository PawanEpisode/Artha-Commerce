"""Idempotency keys: the same moment always yields the same key, so replaying an event never notifies twice."""

from __future__ import annotations

from .catalogue import EventSpec

MAX_KEY_LENGTH = 120  # matches the database column


def build_dedupe_key(spec: EventSpec, **parts: object) -> str:
    try:
        key = spec.dedupe_template.format(**{name: str(value) for name, value in parts.items()})
    except KeyError as missing:
        raise ValueError(f"Event {spec.key} needs the part {missing} to build its dedupe key") from None
    if len(key) > MAX_KEY_LENGTH:
        raise ValueError(f"Dedupe key for {spec.key} is longer than {MAX_KEY_LENGTH} characters")
    return key
