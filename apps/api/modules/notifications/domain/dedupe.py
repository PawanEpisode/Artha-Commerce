"""Idempotency keys: the same moment always yields the same key, so replaying an event never notifies twice."""

from __future__ import annotations

from collections.abc import Mapping
from string import Formatter

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


def placeholders(spec: EventSpec) -> tuple[str, ...]:
    """The part names a template needs, in order (`evaluation:{attempt_id}` -> `("attempt_id",)`)."""
    return tuple(dict.fromkeys(name for _, name, _, _ in Formatter().parse(spec.dedupe_template) if name))


def normalize_parts(spec: EventSpec, ref: object) -> dict[str, object]:
    """
    Accepts what `notify(..., dedupe_ref=...)` receives: a mapping of parts, or a single value for a template that has
    exactly one placeholder.
    """
    if isinstance(ref, Mapping):
        return dict(ref)
    names = placeholders(spec)
    if len(names) != 1:
        raise ValueError(f"Event {spec.key} needs a mapping of {names or 'no parts'} as its dedupe reference")
    return {names[0]: ref}
