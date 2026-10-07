"""Tags (ERD 2.8): a student's own labels, at most `max_tags`, applied to notes through `ItemTag`."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound

from ..domain.tags import clean_tag_name, normalise_tag
from ..errors import TagExists, UnknownTag
from ..models import ItemTag, Note, Tag
from . import quota


def create_tag(user_id, name: str, color_key: str | None = None) -> tuple[Tag, bool]:
    """Idempotent on the normalised name: returns the existing tag (created False) instead of failing."""
    display, norm = clean_tag_name(name), normalise_tag(name)
    existing = Tag.objects.filter(user_id=user_id, name_norm=norm).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            quota.reserve_tag(user_id)
            return Tag.objects.create(user_id=user_id, name=display, name_norm=norm, color_key=color_key), True
    except IntegrityError:  # lost a race for the same name: the quota reservation rolled back with it
        return Tag.objects.get(user_id=user_id, name_norm=norm), False


@transaction.atomic
def update_tag(user_id, tag_id, changes: dict) -> Tag:
    tag = Tag.objects.select_for_update().filter(pk=tag_id, user_id=user_id).first()
    if tag is None:
        raise NotFound("Tag not found.")
    if "name" in changes:
        norm = normalise_tag(changes["name"])
        if Tag.objects.filter(user_id=user_id, name_norm=norm).exclude(pk=tag.pk).exists():
            raise TagExists
        tag.name, tag.name_norm = clean_tag_name(changes["name"]), norm
    if "color_key" in changes:
        tag.color_key = changes["color_key"]
    tag.save()
    return tag


@transaction.atomic
def delete_tag(user_id, tag_id) -> None:
    deleted, _ = Tag.objects.filter(pk=tag_id, user_id=user_id).delete()  # cascades the item links
    if not deleted:
        raise NotFound("Tag not found.")
    quota.release_tag(user_id)


def owned_tags(user_id, tag_ids: Iterable[UUID]) -> list[Tag]:
    """The student's tags among `tag_ids`; any id that is not theirs is `unknown_tag` (422), never a leak."""
    wanted = list(dict.fromkeys(tag_ids))
    found = {t.id: t for t in Tag.objects.filter(user_id=user_id, pk__in=wanted)}
    if len(found) != len(wanted):
        raise UnknownTag
    return [found[i] for i in wanted]


@transaction.atomic
def set_note_tags(user_id, note: Note, tag_ids: Iterable[UUID]) -> list[Tag]:
    """Replace the note's tag set. Idempotent: the same list twice changes nothing."""
    tags = owned_tags(user_id, tag_ids)
    keep = {t.id for t in tags}
    ItemTag.objects.filter(note=note).exclude(tag_id__in=keep).delete()
    have = set(ItemTag.objects.filter(note=note).values_list("tag_id", flat=True))
    ItemTag.objects.bulk_create(
        [ItemTag(user_id=user_id, tag=t, note=note) for t in tags if t.id not in have], ignore_conflicts=True
    )
    return tags


@transaction.atomic
def set_annotation_tags(user_id, annotation, tag_ids: Iterable[UUID]) -> bool:
    """
    Replace a mark's tag set (every id must be the student's: `unknown_tag` otherwise, which is also what a foreign id
    answers). Returns whether anything changed, so a replayed write stays a no-op.
    """
    tags = owned_tags(user_id, tag_ids)
    keep = {t.id for t in tags}
    have = set(ItemTag.objects.filter(annotation=annotation).values_list("tag_id", flat=True))
    if keep == have:
        return False
    ItemTag.objects.filter(annotation=annotation).exclude(tag_id__in=keep).delete()
    ItemTag.objects.bulk_create(
        [ItemTag(user_id=user_id, tag=t, annotation=annotation) for t in tags if t.id not in have],
        ignore_conflicts=True,
    )
    return True
