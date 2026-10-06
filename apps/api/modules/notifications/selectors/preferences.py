from __future__ import annotations

from ..domain.catalogue import CATEGORIES, Overrides, is_enabled
from ..domain.enums import Channel
from ..models import Preference


def overrides(user_id) -> dict[tuple[str, str], bool]:
    rows = Preference.objects.filter(user_id=user_id).values_list("category", "channel", "enabled")
    return {(category, channel): enabled for category, channel, enabled in rows}


def category_view(user_id, *, overrides_: Overrides | None = None) -> list[dict]:
    """The catalogue merged with the student's choices, in display order."""
    chosen = overrides(user_id) if overrides_ is None else overrides_
    return [
        {
            "key": spec.key.value,
            "label": spec.label,
            "description": spec.description,
            "channels": {channel.value: is_enabled(spec.key.value, channel.value, chosen) for channel in Channel},
        }
        for spec in CATEGORIES
    ]
