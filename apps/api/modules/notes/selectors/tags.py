"""Tags of a student with how many live notes carry each."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Q

from ..models import Tag


@dataclass(frozen=True)
class TagView:
    tag: Tag
    count: int


def list_tags(user_id) -> list[TagView]:
    rows = (
        Tag.objects.filter(user_id=user_id)
        .annotate(live=Count("items", filter=Q(items__note__deleted_at__isnull=True)))
        .order_by("name_norm", "id")
    )
    return [TagView(t, t.live) for t in rows]


def get_tag(user_id, tag_id) -> TagView | None:
    return next((v for v in list_tags(user_id) if v.tag.id == tag_id), None)
