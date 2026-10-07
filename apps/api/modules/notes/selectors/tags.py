"""Tags of a student with how many live notes, marks and documents carry each."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Q

from ..models import Tag

# An item counts when it is a live note, a live mark or a live document (the item row has exactly one target).
_LIVE_ITEM = (
    Q(items__note__isnull=False, items__note__deleted_at__isnull=True)
    | Q(items__annotation__isnull=False, items__annotation__deleted_at__isnull=True)
    | Q(items__document__isnull=False, items__document__deleted_at__isnull=True)
)


@dataclass(frozen=True)
class TagView:
    tag: Tag
    count: int


def list_tags(user_id) -> list[TagView]:
    rows = (
        Tag.objects.filter(user_id=user_id).annotate(live=Count("items", filter=_LIVE_ITEM)).order_by("name_norm", "id")
    )
    return [TagView(t, t.live) for t in rows]


def get_tag(user_id, tag_id) -> TagView | None:
    return next((v for v in list_tags(user_id) if v.tag.id == tag_id), None)
