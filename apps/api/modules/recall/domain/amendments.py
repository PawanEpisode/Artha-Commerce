"""
Pure rules of the amendment port (R2-W2, FR-F15-49). F-14 is not built, so recall listens to its events by name; this module
holds what recall decides from an event's payload. Payload fields are those of the F-14 ERD events section (`amendment_id`,
`revision_id`, `chapter_ids[]`, `provision_keys[]`); `provision_keys[]` is a PROPOSED extension and may be missing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

PUBLISHED, CORRECTED, RETRACTED = "amendment_published", "amendment_corrected", "amendment_retracted"
FLAG_CHUNK = 1000  # cards per `recall.flag_amendment` job (ERD 6.4)
MAX_KEYS = 500  # more provision keys than this in one event are ignored beyond the first 500


def normalise_keys(keys: Iterable[object] | None) -> list[str]:
    """Provision keys as recall stores them on an item (`clean_reference_keys`): trimmed, lower case, unique, in order."""
    out: list[str] = []
    for raw in keys or ():
        key = raw.strip().lower() if isinstance(raw, str) else ""
        if key and key not in out:
            out.append(key)
    return out[:MAX_KEYS]


def is_relevant(kind: str, *, material: bool | None) -> bool:
    """A published amendment and a retraction always count; a correction only when F-14 says it is material."""
    if kind == CORRECTED:
        return material is True
    return kind in (PUBLISHED, RETRACTED)


def matches_keys(item_keys: Sequence[str], provision_keys: Sequence[str]) -> bool:
    """True when the item's reference keys and the event's provision keys share one."""
    return bool(set(normalise_keys(item_keys)) & set(provision_keys))


def match_mode(provision_keys: Sequence[str]) -> str:
    """Platform items are matched by provision key when the event carries any, else by chapter."""
    return "keys" if provision_keys else "chapters"


def event_key(kind: str, amendment_id: object, revision_id: object | None) -> str:
    """The idempotency key of one event: the same event twice queues one job, and a job twice flags once."""
    return f"{kind}:{amendment_id}:{revision_id or '-'}"
