"""
Note writes (ERD 3.2, 3.6). Every write locks the note row, validates the body at the edge of the domain and writes the note,
its version row, its image and tag rows in one transaction. Quota is a conditional UPDATE (`services.quota`). Counts events go
out after commit and only when a chapter's counts really change (create, trash, restore, move).

Concurrency rule for `update_note`: the client sends the `rev` it last saw. The same rev is accepted as is. An older rev means
another device wrote in between: scalar fields are last-write-wins (reported when the client sent `base` values), and the body
is merged three ways from the version row at that rev (or the `base_body_md` the client sends). A clean merge is accepted; an
overlap raises `NoteConflict` and writes nothing. Editing a trashed note restores it: an edit never loses to a delete.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from .. import events
from ..domain import merge
from ..errors import NoteConflict
from ..models import Note, NoteVersion
from . import body as bodies
from . import images, links, quota, search_index, tags, versions

SCALARS = ("title", "pinned", "chapter_id", "topic_id")
RESOLUTIONS = ("mine", "theirs", "both")


def _now() -> datetime:
    return timezone.now()


@dataclass(frozen=True)
class UpdateResult:
    note: Note
    merged: bool = False
    restored: bool = False
    overwritten: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CreateResult:
    note: Note
    created: bool


def get_locked(user_id, note_id) -> Note:
    note = Note.objects.select_for_update().filter(pk=note_id, user_id=user_id).first()
    if note is None:
        raise NotFound("Note not found.")
    return note


# --- Create ---------------------------------------------------------------------------------------------------------------
def create_note(
    user_id,
    *,
    client_id: UUID,
    title: str = "",
    body_md: str = "",
    chapter_id: UUID | None = None,
    topic_id: UUID | None = None,
    tag_ids: Iterable[UUID] = (),
    origin: str = Note.Origin.TYPED,
    clip_source: Mapping[str, str] | None = None,
) -> CreateResult:
    """Idempotent on `client_id`: a replay returns the stored note (created False) and takes no quota."""
    existing = Note.objects.filter(user_id=user_id, client_id=client_id).first()
    if existing:
        return CreateResult(existing, False)
    title = bodies.clean_title(title)
    body = bodies.prepare_body(user_id, body_md, title, quota.limits_for(user_id))
    link = links.link_columns(chapter_id, topic_id)
    now = _now()
    try:
        with transaction.atomic():
            quota.reserve_note(user_id)
            note = Note.objects.create(
                user_id=user_id,
                client_id=client_id,
                origin=origin,
                title=title,
                body_md=body.md,
                body_text=body.text,
                body_chars=body.chars,
                lang=body.lang,
                clip_source=dict(clip_source) if clip_source else None,
                **link,
            )
            versions.record(note, source=NoteVersion.Source.MANUAL, now=now)
            images.sync(note, body)
            tags.set_note_tags(user_id, note, tag_ids)
            search_index.refresh(note)
            events.announce_counts(user_id, [note.link_key()], "created")
    except IntegrityError:  # a retry of the same client_id raced us; the quota reservation rolled back with it
        existing = Note.objects.filter(user_id=user_id, client_id=client_id).first()
        if existing is None:
            raise
        return CreateResult(existing, False)
    return CreateResult(note, True)


def create_clip(
    user_id,
    *,
    client_id: UUID,
    text_md: str,
    source: Mapping[str, str],
    chapter_id: UUID | None = None,
    topic_id: UUID | None = None,
    tag_ids: Iterable[UUID] = (),
) -> CreateResult:
    """
    The single entry point for "Save to notes" from other modules (question bank, previous papers, study material,
    amendments). Idempotent on `client_id`. The title is the source's label; the body is the clipped Markdown.
    """
    return create_note(
        user_id,
        client_id=client_id,
        title=source.get("label", ""),
        body_md=text_md,
        chapter_id=chapter_id,
        topic_id=topic_id,
        tag_ids=tag_ids,
        origin=Note.Origin.CLIP,
        clip_source={"module": source["module"], "ref": source["ref"], "label": source.get("label", "")},
    )


# --- Update ---------------------------------------------------------------------------------------------------------------
def _snapshot(note: Note) -> dict[str, Any]:
    return {"rev": note.rev, "title": note.title, "body_md": note.body_md, "updated_at": note.updated_at}


def _conflict(note: Note, mine: Mapping[str, Any], merged_text: str | None = None) -> NoteConflict:
    wanted = {k: mine[k] for k in ("title", "body_md") if k in mine}
    merged = {"body_md": merged_text} if merged_text is not None and merged_text != note.body_md else None
    return NoteConflict(extra={"theirs": _snapshot(note), "mine": wanted, "merged": merged})


def _scalar_view(note: Note) -> dict[str, Any]:
    """The note's scalar fields in the form clients send them (ids as strings), for compare-and-set."""
    return {
        "title": note.title,
        "pinned": note.pinned,
        "chapter_id": str(note.chapter_id) if note.chapter_id else None,
        "topic_id": str(note.topic_id) if note.topic_id else None,
    }


def _resolve_body(
    note: Note, patch: Mapping[str, Any], *, stale: bool, base_body_md: str | None, resolution: str | None
):
    """The body to store (or None for no change), whether it was merged, and the version source for it."""
    mine = bodies.derive_body(patch["body_md"]).md
    if mine == note.body_md:
        return None, False, None
    if resolution == "both":
        return merge.both(note.body_md, mine), False, NoteVersion.Source.MERGE
    if not stale:
        return mine, False, None
    base = (
        bodies.derive_body(base_body_md).md if base_body_md is not None else versions.body_at(note, patch["_base_rev"])
    )
    if base is None:
        raise _conflict(note, patch)
    result = merge.merge3_text(base, mine, note.body_md)
    if not result.clean:
        raise _conflict(note, patch, result.text)
    return result.text, result.text != mine, NoteVersion.Source.MERGE


def _resolve_scalars(note: Note, patch: Mapping[str, Any], base: Mapping[str, Any] | None):
    mine = {k: patch[k] for k in SCALARS if k in patch}
    if "title" in mine:
        mine["title"] = bodies.clean_title(mine["title"])
    for key in ("chapter_id", "topic_id"):
        if key in mine and mine[key] is not None:
            mine[key] = str(mine[key])
    result = merge.merge_fields(base or {}, mine, _scalar_view(note))
    return result.values, result.overwritten


@transaction.atomic
def update_note(
    user_id,
    note_id,
    *,
    base_rev: int,
    patch: Mapping[str, Any],
    base_body_md: str | None = None,
    base: Mapping[str, Any] | None = None,
    source: str = NoteVersion.Source.AUTOSAVE,
    resolution: str | None = None,
) -> UpdateResult:
    """`patch` holds only the fields to change (title, body_md, chapter_id, topic_id, pinned, tag_ids). See the module doc."""
    note = get_locked(user_id, note_id)
    stale = base_rev != note.rev
    if resolution and stale:
        raise _conflict(note, patch)  # the client resolved against an older `theirs`: show it the current one
    if resolution == "theirs":
        return UpdateResult(note)
    restored = note.is_trashed
    old_key = None if restored else note.link_key()
    new_body, merged, body_source = (None, False, None)
    if "body_md" in patch:
        new_body, merged, body_source = _resolve_body(
            note, {**patch, "_base_rev": base_rev}, stale=stale, base_body_md=base_body_md, resolution=resolution
        )
    values, overwritten = _resolve_scalars(note, patch, base)
    changes = _field_changes(note, values)
    tag_ids = patch.get("tag_ids")
    if new_body is None and not changes and tag_ids is None and not restored:
        return UpdateResult(note)  # a replay of an accepted write: nothing to do, rev unchanged
    return _apply(
        note, user_id, new_body=new_body, changes=changes, tag_ids=tag_ids, restored=restored, merged=merged,
        overwritten=overwritten, source=body_source or source, old_key=old_key,
    )  # fmt: skip


def _field_changes(note: Note, values: Mapping[str, Any]) -> dict[str, Any]:
    """Model fields to write for the scalar values that differ from what is stored."""
    changes: dict[str, Any] = {}
    if "title" in values and values["title"] != note.title:
        changes["title"] = values["title"]
    if "pinned" in values and values["pinned"] != note.pinned:
        changes["pinned"] = values["pinned"]
    if "chapter_id" in values or "topic_id" in values:
        chapter = values.get("chapter_id", str(note.chapter_id) if note.chapter_id else None)
        topic = values.get(
            "topic_id", None if "chapter_id" in values else (str(note.topic_id) if note.topic_id else None)
        )
        link = links.link_columns(UUID(chapter) if chapter else None, UUID(topic) if topic else None)
        if any(getattr(note, name) != value for name, value in link.items()):
            changes.update(link)
    return changes


def _apply(
    note, user_id, *, new_body, changes, tag_ids, restored, merged, overwritten, source, old_key
) -> UpdateResult:
    if restored:
        quota.reserve_note(user_id)  # an edit beats the trash, but the quota still applies
        note.deleted_at = note.purge_after = None
    body = None
    if new_body is not None:
        body = bodies.prepare_body(user_id, new_body, changes.get("title", note.title), quota.limits_for(user_id))
        note.body_md, note.body_text, note.body_chars, note.lang = body.md, body.text, body.chars, body.lang
    for name, value in changes.items():
        setattr(note, name, value)
    note.rev += 1
    note.save()
    versions.record(note, source=source, now=_now())
    if body is not None:
        images.sync(note, body)
    if tag_ids is not None:
        tags.set_note_tags(user_id, note, tag_ids)
    if new_body is not None or "title" in changes or restored:
        if body is None:
            note.lang = bodies.derive_body(note.body_md, note.title).lang
            note.save(update_fields=["lang"])
        search_index.refresh(note)
    if restored:
        events.announce_counts(user_id, [note.link_key()], "restored")
    elif "chapter_id" in changes:
        events.announce_counts(user_id, [old_key], "relinked")
        events.announce_counts(user_id, [note.link_key()], "relinked")
    return UpdateResult(note, merged=merged, restored=restored, overwritten=overwritten)


@transaction.atomic
def restore_version(user_id, note_id, rev: int) -> Note:
    """Makes the text of an old version the head again as a NEW version (source `restore`); nothing is deleted."""
    note = get_locked(user_id, note_id)
    if note.is_trashed:
        raise NotFound("Note not found.")
    old = NoteVersion.objects.filter(note=note, rev=rev).first()
    if old is None:
        raise NotFound("Version not found.")
    body = bodies.derive_body(old.body_md, old.title)
    note.title, note.body_md, note.body_text, note.body_chars, note.lang = (
        old.title,
        body.md,
        body.text,
        body.chars,
        body.lang,
    )
    note.rev += 1
    note.save()
    versions.record(note, source=NoteVersion.Source.RESTORE, now=_now())
    images.sync(note, body)
    search_index.refresh(note)
    return note


@transaction.atomic
def retag_note(user_id, note_id, tag_ids: Iterable[UUID]) -> Note:
    """Replaces a note's tags and counts as a change (rev and `updated_at` move), so the changes feed carries it."""
    note = get_locked(user_id, note_id)
    tags.set_note_tags(user_id, note, tag_ids)
    note.rev += 1
    note.save()
    versions.record(note, source=NoteVersion.Source.MANUAL, now=_now())
    return note
