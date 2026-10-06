"""Per-category, per-channel switches. Only changes from the catalogue default are stored."""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction

from ..domain.catalogue import UnknownSwitch, is_default_enabled, validate_switch
from ..errors import InvalidSettings
from ..models import Preference


def set_preferences(user_id, items: Iterable[tuple[str, str, bool]]) -> int:
    """Apply `(category, channel, enabled)` triples atomically. Returns how many were applied. Unknown pair: 400."""
    parsed: dict[tuple[str, str], bool] = {}
    errors: dict[str, str] = {}
    for category, channel, enabled in items:
        try:
            cat, chan = validate_switch(category, channel)
        except UnknownSwitch as exc:
            errors[f"{category}.{channel}"] = str(exc)
            continue
        parsed[(cat.value, chan.value)] = enabled
    if errors:
        raise InvalidSettings("Unknown notification switch.", extra=errors)
    with transaction.atomic():
        for (category, channel), enabled in parsed.items():
            if enabled == is_default_enabled(category, channel):
                Preference.objects.filter(user_id=user_id, category=category, channel=channel).delete()
            else:
                Preference.objects.update_or_create(
                    user_id=user_id, category=category, channel=channel, defaults={"enabled": enabled}
                )
    return len(parsed)
