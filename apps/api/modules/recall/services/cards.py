"""
Card writes (PRD 9.2, ERD 3.2). One place creates, edits, changes the status of and deletes a student's cards; views call
these functions and never touch the ORM.

Rules that hold for every function here
- One transaction per call. Quota is reserved first with the conditional updates of `services.quota`, inside a savepoint, so
  any later failure (a duplicate client id, a bad deck, a constraint) rolls the reservation back with it.
- The scheduling rules live in `domain`; nothing here does scheduling arithmetic. A new card stays in state 0 with no
  stability and no due time. Editing text never changes the memory columns.
- Another student's card is `NotFound` (404), a deleted one `CardDeleted` (410).
- Undo tokens are stateless: `django.core.signing` with salt `recall.undo`, a 10 second max age and the card and student ids
  inside, so there is nothing to store or to clean up. The same token mechanism undoes a delete (restores the item and
  re-reserves its quota) and a just-created selection card (deletes it). Card text never appears in a log or an exception.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import richtext
from core.recall_port import SourceRef

from .. import registry
from ..adapters import syllabus as syllabus_adapter
from ..domain import cards as domain
from ..domain import limits as lim
from ..domain import scheduling
from ..errors import (
    BulkTooLarge,
    CardDeleted,
    EditConflict,
    InvalidFields,
    UndoExpired,
)
from ..errors import DuplicateCard as DuplicateCardError
from ..models import (
    ITEM_IMPORTANCES,
    ITEM_ORIGINS,
    RecallCard,
    RecallDeck,
    RecallDeckItem,
    RecallItem,
    RecallItemVersion,
    RecallParams,
    RecallScheduleEvent,
)
from ..vocab import IMPORTANCE_INT
from . import quota, student

UNDO_SECONDS = 10
UNDO_SALT = "recall.undo"
BULK_MAX = 200
MAX_REFERENCE_KEYS = 20
REFERENCE_KEY_MAX_CHARS = 80
BURY_MAX_DAYS = 7
SEARCH_TEXT_MAX = 10_000
BULK_ACTIONS = ("move_chapter", "set_importance", "add_tag", "suspend", "delete", "add_to_deck")
STATUS_ACTIONS = ("suspend", "unsuspend", "bury", "reset", "recheck_ok", "delete")
SELECTION_ORIGINS = {
    "note_highlight": "selection",
    "solution_text": "solution",
    "chapter_page": "selection",
    "question_review": "mistake",
}
ORIGIN_MODULES = {"notes", "questionbank", "amendments", "study_material", "super50"}


class _Unset:
    def __repr__(self) -> str:
        return "UNSET"


UNSET: Any = _Unset()  # "not sent", as opposed to None ("clear it")


def _now() -> datetime:
    return timezone.now()


@dataclass(frozen=True)
class SelectionSource:
    """Where a selection came from: ids and offsets only, never any of its text (ERD 3.2)."""

    module: str
    object_id: str
    locator: dict = field(default_factory=dict)


@dataclass
class CreatedCards:
    item: RecallItem
    cards: list[RecallCard]
    existing: bool = False
    undo_token: str | None = None

    @property
    def card_id(self) -> UUID:
        return self.cards[0].id

    @property
    def item_id(self) -> UUID:
        return self.item.id

    @property
    def kind(self) -> str:
        return self.item.kind


@dataclass(frozen=True)
class BulkResult:
    count: int
    ids: tuple[UUID, ...]


# --------------------------------------------------------------------------------------------------- validation
def _issue(field_name: str, code: str, message: str, line: int | None = None) -> dict:
    return {"field": field_name, "code": code, "message": message, "line": line}


def _refuse(issues: list[dict]) -> None:
    if issues:
        raise InvalidFields(extra={"errors": issues})


def clean_fields(spec: registry.KindSpec, raw: dict) -> dict:
    """Sanitised copy of the fields a student sent (the version marker is ours, never taken from the client)."""
    out: dict = {}
    for name, value in raw.items():
        if name == "v":
            continue
        out[name] = richtext.sanitise(value).strip() if isinstance(value, str) else value
    return out


def check_fields(spec: registry.KindSpec, fields: dict) -> None:
    """Kind rules first, then the `card` Markdown profile on every Markdown field. 422 `invalid_fields` with per-field issues."""
    issues = [_issue(i.field, i.code, i.message) for i in spec.validate(fields)]
    for name in spec.markdown_fields:
        value = fields.get(name)
        if isinstance(value, str) and value and not any(i["field"] == name for i in issues):
            issues += [
                _issue(name, i.code, i.message, i.line) for i in richtext.errors_of(richtext.lint(value, "card"))
            ]
    _refuse(issues)


def clean_tags(tags: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for raw in tags:
        tag = " ".join(str(raw).split()) if isinstance(raw, str) else ""
        if not tag:
            _refuse([_issue("tags", "bad_tag", "A tag must be some text.")])
        if len(tag) > lim.MAX_TAG_CHARS:
            _refuse([_issue("tags", "tag_too_long", f"A tag has at most {lim.MAX_TAG_CHARS} characters.")])
        if tag.lower() not in {t.lower() for t in out}:
            out.append(tag)
    if len(out) > lim.MAX_TAGS:
        _refuse([_issue("tags", "too_many_tags", f"At most {lim.MAX_TAGS} tags are allowed.")])
    return out


def clean_reference_keys(keys: Iterable[Any]) -> list[str]:
    out: list[str] = []
    for raw in keys:
        key = raw.strip().lower() if isinstance(raw, str) else ""
        if not key or len(key) > REFERENCE_KEY_MAX_CHARS:
            _refuse(
                [_issue("reference_keys", "bad_reference_key", "A reference key is text of at most 80 characters.")]
            )
        if key not in out:
            out.append(key)
    if len(out) > MAX_REFERENCE_KEYS:
        _refuse([_issue("reference_keys", "too_many_reference_keys", f"At most {MAX_REFERENCE_KEYS} are allowed.")])
    return out


def clean_importance(importance: str) -> str:
    if importance not in ITEM_IMPORTANCES:
        _refuse([_issue("importance", "bad_importance", "Importance is bullet, important or mandatory.")])
    return importance


def plain_text_of(spec: registry.KindSpec, fields: dict) -> str:
    parts = []
    for f in spec.fields:
        value = fields.get(f.name)
        if isinstance(value, str) and value:
            parts.append(value if f.short else richtext.plain_text(value))
    return "\n".join(parts)


def content_hash(fields: dict) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def clean_locator(locator: dict | None) -> dict | None:
    """Keep ids, numbers and short offsets only: a locator can never smuggle text in (ERD 2.1)."""
    if not locator:
        return None
    out: dict = {"v": 1}
    for key, value in locator.items():
        if not isinstance(key, str) or len(key) > 40 or key == "v":
            continue
        if isinstance(value, (bool, int, float)) or value is None:
            out[key] = value
        elif isinstance(value, str) and len(value) <= 80:
            out[key] = value
        elif isinstance(value, list) and len(value) <= 4 and all(isinstance(x, (int, float)) for x in value):
            out[key] = value
    return out


# --------------------------------------------------------------------------------------------------- small queries
def _default_params() -> RecallParams | None:
    return RecallParams.objects.filter(scope="default", status="active").first()


def _cards_of(item: RecallItem, *, with_deleted: bool = False) -> list[RecallCard]:
    qs = RecallCard.objects.filter(item=item, user_id=item.owner_user_id).order_by("ordinal")
    return list(qs if with_deleted else qs.exclude(status="deleted"))


def _existing(user_id, client_id, source: SourceRef | None, origin_kind: str | None) -> CreatedCards | None:
    item = RecallItem.objects.filter(owner_user_id=user_id, client_id=client_id).first() if client_id else None
    if item is None and source is not None and origin_kind:
        item = RecallItem.objects.filter(
            owner_user_id=user_id,
            origin_module=source.module,
            origin_ref=str(source.ref_id),
            origin_kind=origin_kind,
            status__in=["active", "archived"],
        ).first()
    if item is None:
        return None
    return CreatedCards(item, _cards_of(item, with_deleted=True) or [], existing=True)


def _own_decks(user_id, deck_ids: Sequence[UUID]) -> list[RecallDeck]:
    wanted = list(dict.fromkeys(deck_ids))
    if not wanted:
        return []
    decks = list(
        RecallDeck.objects.filter(pk__in=wanted, owner_user_id=user_id, kind="user", deleted_at__isnull=True).exclude(
            status="withdrawn"
        )
    )
    if len(decks) != len(wanted):
        raise NotFound("Deck not found.")
    return decks


def _deck_ids_of(item: RecallItem) -> list[UUID]:
    return list(RecallDeckItem.objects.filter(item=item).values_list("deck_id", flat=True))


# --------------------------------------------------------------------------------------------------- create
def create_card(
    user_id,
    *,
    kind: str,
    fields: dict,
    chapter_id: UUID | None = None,
    topic_id: UUID | None = None,
    importance: str = "bullet",
    tags: Iterable[Any] = (),
    reference_keys: Iterable[Any] = (),
    deck_ids: Sequence[UUID] = (),
    client_id: UUID | None,
    force: bool = False,
    origin: str = "manual",
    source: SourceRef | None = None,
    origin_kind: str | None = None,
    origin_locator: dict | None = None,
    origin_module: str | None = None,
    origin_ref: str | None = None,
    shareable: bool | None = None,
) -> CreatedCards:
    """
    Create an item with its first live version and one card per face (a cloze gives several). Idempotent on
    `(student, client_id)` (and on the source key when `source` and `origin_kind` are given): a replay returns the first
    result with `existing=True`. 409 `duplicate_card` unless `force`; 429 `quota_exceeded` when the plan is full.
    """
    if origin not in ITEM_ORIGINS:
        raise ValueError(f"unknown origin {origin!r}")
    with transaction.atomic():
        prior = _existing(user_id, client_id, source, origin_kind)
        if prior is not None:
            return prior
        spec = registry.get_kind(kind)
        clean = clean_fields(spec, fields)
        check_fields(spec, clean)
        importance = clean_importance(importance)
        tag_list = clean_tags(tags)
        key_list = clean_reference_keys(reference_keys)
        link = syllabus_adapter.link_columns(chapter_id, topic_id)
        fp = domain.fingerprint(kind, clean)
        if not force:
            _refuse_duplicate(user_id, fp)
        decks = _own_decks(user_id, deck_ids)
        faces = spec.ordinals(clean)
        if source is not None:
            origin_module, origin_ref = source.module, str(source.ref_id)
        if origin_module not in ORIGIN_MODULES:
            origin_module = origin_ref = None
        try:
            with transaction.atomic():  # a failure below undoes the quota reservation with it
                quota.reserve_cards(user_id, len(faces))
                for deck in decks:
                    quota.reserve_deck_member(user_id, deck.id, len(faces))
                return _insert(
                    user_id,
                    kind=kind,
                    spec=spec,
                    fields=clean,
                    faces=faces,
                    link=link,
                    importance=importance,
                    tags=tag_list,
                    reference_keys=key_list,
                    decks=decks,
                    client_id=client_id,
                    fp=fp,
                    origin=origin,
                    origin_module=origin_module,
                    origin_ref=origin_ref,
                    origin_kind=origin_kind,
                    origin_locator=clean_locator(origin_locator),
                    shareable=(origin == "manual" and source is None) if shareable is None else shareable,
                )
        except IntegrityError:
            prior = _existing(user_id, client_id, source, origin_kind)
            if prior is None:
                raise
            return prior


def _refuse_duplicate(user_id, fp: str) -> None:
    item = RecallItem.objects.filter(
        owner_user_id=user_id, ownership="user", fingerprint=fp, status__in=["active", "archived"]
    ).first()
    if item is None:
        return
    card = RecallCard.objects.filter(item=item, user_id=user_id).exclude(status="deleted").order_by("ordinal").first()
    if card is not None:
        raise DuplicateCardError(extra={"card_id": str(card.id), "item_id": str(item.id)})


def _insert(
    user_id, *, kind, spec, fields, faces, link, importance, tags, reference_keys, decks, client_id, fp, **origin
):
    now = _now()
    item = RecallItem.objects.create(
        kind=kind,
        ownership="user",
        owner_user_id=user_id,
        origin=origin["origin"],
        status="active",
        importance=importance,
        rights_status="original",
        origin_module=origin["origin_module"],
        origin_ref=origin["origin_ref"],
        origin_kind=origin["origin_kind"],
        origin_locator=origin["origin_locator"],
        shareable=origin["shareable"],
        tags=tags,
        reference_keys=reference_keys,
        fingerprint=fp,
        search_text=plain_text_of(spec, fields)[:SEARCH_TEXT_MAX],
        client_id=client_id,
        created_by=user_id,
        **link,
    )
    version = RecallItemVersion.objects.create(
        item=item,
        version_no=1,
        state="live",
        change_kind="create",
        fields={"v": domain.FIELDS_VERSION, **fields},
        fields_schema=domain.FIELDS_VERSION,
        cloze_count=len(faces) if kind == "cloze" else 0,
        content_hash=content_hash(fields),
        plain_text=plain_text_of(spec, fields),
        authored_by=user_id,
        live_at=now,
    )
    item.live_version = item.current_version = version
    item.save(update_fields=["live_version", "current_version", "updated_at"])
    params = _default_params()
    created = RecallCard.objects.bulk_create(
        [
            RecallCard(
                user_id=user_id,
                item=item,
                ordinal=ordinal,
                item_version=version,
                chapter_id=link["chapter_id"],
                subject_key=link["subject_key"],
                importance=IMPORTANCE_INT[importance],
                scheduler_version=lim.SCHEDULER_VERSION,
                params=params,
            )
            for ordinal in faces
        ]
    )
    RecallDeckItem.objects.bulk_create(
        [RecallDeckItem(deck=deck, item=item, position=deck.card_count) for deck in decks]
    )
    return CreatedCards(item, list(created))


# --------------------------------------------------------------------------------------------------- selection
_SECTION_REF = re.compile(r"\b(?:section|sec\.?|rule|article|regulation)\s+\d+[\w()]*", re.IGNORECASE)
_SEPARATOR = re.compile(r"\s+(?:means|is defined as|are defined as|shall mean|refers to)\s+|:\s+", re.IGNORECASE)
_CASE_SPLIT = re.compile(r"\s+(?:v\.?|vs\.?)\s+", re.IGNORECASE)


def _short(text: str, limit: int = 120) -> str:
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"


def _trim(text: str) -> str:
    return text[: lim.FIELD_MAX_CHARS].rstrip()


def fields_for_selection(kind: str, text: str, *, cloze: bool = False) -> dict:
    """The fields a one-tap card gets from selected text, per kind. Pure; the student can always edit afterwards."""
    text = text.strip()
    found = _SEPARATOR.search(text)
    head, tail = (text[: found.start()], text[found.end() :]) if found else (text, "")
    if kind == "cloze" or cloze:
        body = text[
            : lim.FIELD_MAX_CHARS - 40
        ].rstrip()  # leave room for the markers, so a long text keeps its closing braces
        if domain.CLOZE.search(body):
            return {"text_md": body}
        split = _SEPARATOR.search(body)
        words = body.split()
        if split and body[split.end() :]:
            wrapped = f"{body[: split.end()]}{{{{c1::{body[split.end() :]}}}}}"
        elif len(words) > 3:
            wrapped = " ".join(words[:-3]) + " {{c1::" + " ".join(words[-3:]) + "}}"
        else:
            wrapped = "{{c1::" + body + "}}"
        return {"text_md": wrapped}
    if kind == "formula":
        return {"name": _short(head if tail else text, 80), "expression_md": _trim(text)}
    if kind == "definition":
        return (
            {"term": _short(head, 80), "definition_md": _trim(tail)}
            if tail
            else {"term": _short(" ".join(text.split()[:6]), 80), "definition_md": _trim(text)}
        )
    if kind == "section":
        match = _SECTION_REF.search(text)
        return {
            "reference": _short(match.group(0) if match else "Reference", 80),
            "prompt_md": "What does it say?",
            "gist_md": _trim(text),
        }
    if kind == "mnemonic":
        return {"mnemonic": _short(text, 80), "expands_md": _trim(text)}
    if kind == "case_law":
        name = _CASE_SPLIT.split(text, maxsplit=1)
        return {
            "case_name": _short(text if len(name) < 2 else f"{name[0]} v. {name[1].split(',')[0]}", 120),
            "held_md": _trim(text),
        }
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) > 1:
        return {"prompt_md": _trim(paragraphs[0]), "answer_md": _trim("\n\n".join(paragraphs[1:]))}
    if tail and len(head) <= 120:
        return {"prompt_md": _trim(head.rstrip("?") + "?"), "answer_md": _trim(tail)}
    return {"prompt_md": "Recall this point.", "answer_md": _trim(text)}


def create_card_from_selection(
    user_id,
    *,
    origin: str,
    selection_text: str,
    source: SelectionSource,
    chapter_id: UUID | None = None,
    topic_id: UUID | None = None,
    kind: str | None = None,
    client_id: UUID,
    force: bool = False,
    cloze: bool = False,
    quick: bool = True,
) -> CreatedCards:
    """
    One tap from a highlight, a solution or a chapter page (ERD 3.2). The kind is suggested by pure rules when not given.
    `quick` means "no form": the call is the same, the web just skips its editor. The card is never shareable; the result carries
    an `undo_token` that deletes it again within 10 seconds.
    """
    item_origin = SELECTION_ORIGINS.get(origin)
    if item_origin is None:
        raise InvalidFields(extra={"errors": [_issue("origin", "bad_origin", "Unknown origin.")]})
    text = richtext.sanitise(selection_text or "").strip()
    if not text:
        raise InvalidFields(extra={"errors": [_issue("selection_text", "required", "Select some text first.")]})
    chosen = kind or domain.suggest_kind(text)[0]
    registry.get_kind(chosen)
    result = create_card(
        user_id,
        kind=chosen,
        fields=fields_for_selection(chosen, text, cloze=cloze),
        chapter_id=chapter_id,
        topic_id=topic_id,
        client_id=client_id,
        force=force,
        origin=item_origin,
        origin_module=source.module,
        origin_ref=str(source.object_id)[:80],
        origin_locator=source.locator,
        shareable=False,
    )
    if not result.existing:
        result.undo_token = _sign("create", result.card_id, user_id)
    return result


# --------------------------------------------------------------------------------------------------- undo tokens
def _sign(action: str, card_id, user_id) -> str:
    return signing.dumps({"a": action, "c": str(card_id), "u": str(user_id)}, salt=UNDO_SALT, compress=False)


def _unsign(user_id, token: str) -> dict:
    try:
        payload = signing.loads(token, salt=UNDO_SALT, max_age=UNDO_SECONDS)
    except signing.SignatureExpired:
        raise UndoExpired from None
    except signing.BadSignature:
        raise NotFound("Not found.") from None
    if payload.get("u") != str(user_id):
        raise NotFound("Not found.")
    return payload


# --------------------------------------------------------------------------------------------------- locking
def _lock_card(user_id, card_id) -> RecallCard:
    """The student's card, row-locked, or 404 / 410. Another student's id is indistinguishable from a missing one."""
    card = (
        RecallCard.objects.select_for_update(of=("self",))
        .select_related("item", "item_version")
        .filter(pk=card_id, user_id=user_id)
        .first()
    )
    if card is None:
        raise NotFound("Card not found.")
    if card.status == "deleted":
        raise CardDeleted
    return card


def _lock_cards(user_id, ids: Sequence[UUID]) -> list[RecallCard]:
    wanted = set(ids)
    cards = list(
        RecallCard.objects.select_for_update(of=("self",))
        .select_related("item")
        .filter(pk__in=wanted, user_id=user_id)
        .exclude(status="deleted")
        .order_by("pk")
    )
    if len(cards) != len(wanted):
        raise NotFound("Card not found.")
    return cards


def _items_of(cards: Iterable[RecallCard]) -> list[RecallItem]:
    seen: dict[UUID, RecallItem] = {}
    for card in cards:
        seen.setdefault(card.item_id, card.item)
    return list(seen.values())


# --------------------------------------------------------------------------------------------------- metadata helpers
def _apply_link(items: Sequence[RecallItem], link: dict, now: datetime) -> None:
    for item in items:
        for name, value in link.items():
            setattr(item, name, value)
        item.save(update_fields=[*link, "updated_at"])
    RecallCard.objects.filter(item__in=items).update(
        chapter_id=link["chapter_id"], subject_key=link["subject_key"], updated_at=now
    )


def _apply_importance(items: Sequence[RecallItem], importance: str, now: datetime) -> None:
    for item in items:
        item.importance = importance
        item.save(update_fields=["importance", "updated_at"])
    RecallCard.objects.filter(item__in=items).update(importance=IMPORTANCE_INT[importance], updated_at=now)


def _apply_tags(items: Sequence[RecallItem], tags: list[str], now: datetime, *, add: bool) -> None:
    for item in items:
        new = clean_tags([*item.tags, *tags]) if add else tags
        if new != item.tags:
            item.tags = new
            item.save(update_fields=["tags", "updated_at"])


def _bump(items: Sequence[RecallItem], now: datetime) -> None:
    """One revision step for every live face of these items: the offline pack compares `rev`, so one edit is one step."""
    RecallCard.objects.filter(item__in=items).exclude(status="deleted").update(rev=F("rev") + 1, updated_at=now)


def _suspend(cards: Sequence[RecallCard], now: datetime) -> None:
    for card in cards:
        if card.status != "active":
            continue
        card.status, card.suspend_reason = "suspended", "manual"
        card.rev += 1
        card.save(update_fields=["status", "suspend_reason", "rev", "updated_at"])
        RecallScheduleEvent.objects.create(
            user_id=card.user_id, card=card, kind="suspend", at=now, reason_code="student"
        )


def _add_to_deck(user_id, items: Sequence[RecallItem], deck_id: UUID, now: datetime) -> None:
    (deck,) = _own_decks(user_id, [deck_id])
    already = set(RecallDeckItem.objects.filter(deck=deck, item__in=items).values_list("item_id", flat=True))
    for item in items:
        if item.id in already:
            continue
        faces = RecallCard.objects.filter(item=item, user_id=user_id).exclude(status="deleted").count()
        quota.reserve_deck_member(user_id, deck.id, faces)
        RecallDeckItem.objects.create(deck=deck, item=item, position=deck.card_count)
    _bump(items, now)


def _delete_items(user_id, items: Sequence[RecallItem], now: datetime) -> list[UUID]:
    """Soft delete whole items (every face of a cloze goes together) and give their quota back."""
    ids: list[UUID] = []
    for item in items:
        live = list(RecallCard.objects.filter(item=item, user_id=user_id).exclude(status="deleted"))
        if not live:
            continue
        quota.release_cards(user_id, len(live))
        for deck_id in _deck_ids_of(item):
            quota.release_deck_member(user_id, deck_id, len(live))
        item.status, item.deleted_at = "deleted", now
        item.save(update_fields=["status", "deleted_at", "updated_at"])
        RecallCard.objects.filter(item=item, user_id=user_id).exclude(status="deleted").update(
            status="deleted", deleted_at=now, rev=F("rev") + 1, updated_at=now
        )
        ids += [c.id for c in live]
    return ids


# --------------------------------------------------------------------------------------------------- update
def update_card(
    user_id,
    card_id,
    *,
    base_rev: int,
    fields: dict | None = None,
    chapter_id: UUID | None | _Unset = UNSET,
    topic_id: UUID | None | _Unset = UNSET,
    importance: str | None = None,
    tags: Iterable[Any] | None = None,
) -> RecallCard:
    """
    Edit a card against the revision the client saw. A stale `base_rev` is 409 `edit_conflict` with the server's fields and
    revision. A text edit makes a new live version (the old one becomes superseded) and repoints every face; a metadata edit
    only bumps `rev`. Memory state is never touched. Returns the card as stored.
    """
    with transaction.atomic():
        card = _lock_card(user_id, card_id)
        item = card.item
        if base_rev != card.rev:
            raise EditConflict(extra={"server_fields": card.item_version.fields, "rev": card.rev})
        now = _now()
        changed = False
        if fields is not None:
            changed |= _edit_fields(user_id, card, item, fields, now)
        if chapter_id is not UNSET or topic_id is not UNSET:
            new_chapter = item.chapter_id if chapter_id is UNSET else chapter_id
            new_topic = item.topic_id if topic_id is UNSET else topic_id
            if chapter_id is not UNSET and topic_id is UNSET:
                new_topic = None
            link = syllabus_adapter.link_columns(new_chapter, new_topic)
            if (link["chapter_id"], link["topic_id"]) != (item.chapter_id, item.topic_id):
                _apply_link([item], link, now)
                changed = True
        if importance is not None and clean_importance(importance) != item.importance:
            _apply_importance([item], importance, now)
            changed = True
        if tags is not None and (new := clean_tags(tags)) != item.tags:
            _apply_tags([item], new, now, add=False)
            changed = True
        if not changed:
            return card
        _bump([item], now)
        return RecallCard.objects.select_related("item", "item_version").get(pk=card.pk)


def _edit_fields(user_id, card: RecallCard, item: RecallItem, given: dict, now: datetime) -> bool:
    spec = registry.get_kind(item.kind)  # the kind is immutable once live
    old = {k: v for k, v in card.item_version.fields.items() if k != "v"}
    new = clean_fields(spec, {**old, **given})
    if new == old:
        return False
    check_fields(spec, new)
    faces = spec.ordinals(new)
    have = {c.ordinal: c for c in _cards_of(item)}
    removed = sorted(set(have) - set(faces))
    if card.ordinal in removed:
        _refuse([_issue("text_md", "face_removed", "This deletion cannot be removed from its own card.")])
    added = sorted(set(faces) - set(have))
    decks = _deck_ids_of(item)
    if added:
        quota.reserve_cards(user_id, len(added))
        for deck_id in decks:
            quota.reserve_deck_member(user_id, deck_id, len(added))
    previous = item.live_version
    previous.state, previous.superseded_at = "superseded", now
    previous.save(update_fields=["state", "superseded_at", "updated_at"])
    version = RecallItemVersion.objects.create(
        item=item,
        version_no=previous.version_no + 1,
        state="live",
        change_kind="clarify",
        fields={"v": domain.FIELDS_VERSION, **new},
        fields_schema=domain.FIELDS_VERSION,
        cloze_count=len(faces) if item.kind == "cloze" else 0,
        content_hash=content_hash(new),
        plain_text=plain_text_of(spec, new),
        authored_by=user_id,
        live_at=now,
    )
    item.live_version = item.current_version = version
    item.fingerprint = domain.fingerprint(item.kind, new)
    item.search_text = version.plain_text[:SEARCH_TEXT_MAX]
    item.save(update_fields=["live_version", "current_version", "fingerprint", "search_text", "updated_at"])
    RecallCard.objects.filter(item=item, user_id=user_id).exclude(status="deleted").update(
        item_version=version, updated_at=now
    )
    if added:
        RecallCard.objects.bulk_create(
            [
                RecallCard(
                    user_id=user_id,
                    item=item,
                    ordinal=ordinal,
                    item_version=version,
                    chapter_id=item.chapter_id,
                    subject_key=item.subject_key,
                    importance=IMPORTANCE_INT[item.importance],
                    scheduler_version=lim.SCHEDULER_VERSION,
                    params=_default_params(),
                )
                for ordinal in added
            ]
        )
    if removed:
        quota.release_cards(user_id, len(removed))
        for deck_id in decks:
            quota.release_deck_member(user_id, deck_id, len(removed))
        RecallCard.objects.filter(item=item, user_id=user_id, ordinal__in=removed).update(
            status="deleted", deleted_at=now, updated_at=now
        )
    return True


# --------------------------------------------------------------------------------------------------- status
def set_card_status(
    user_id, card_id, action: str, *, until: datetime | None = None
) -> RecallCard | tuple[RecallCard, str]:
    """
    `suspend`, `unsuspend`, `bury` (to the end of the study day unless `until`), `reset` (forget: back to a new card, with a
    `forget` schedule event), `recheck_ok`, `delete` (soft; the result carries an undo token). Returns the card; `delete`
    returns `(card, undo_token)`.
    """
    if action not in STATUS_ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    with transaction.atomic():
        card = _lock_card(user_id, card_id)
        now = _now()
        if action == "delete":
            _delete_items(user_id, [card.item], now)
            card.refresh_from_db()
            return card, _sign("delete", card.id, user_id)
        if action == "suspend":
            _suspend([card], now)
        elif action == "unsuspend":
            _unsuspend(card, now)
        elif action == "bury":
            _bury(user_id, card, now, until)
        elif action == "reset":
            _reset(card, now)
        else:
            card.needs_recheck, card.recheck_reason, card.recheck_ref = False, None, None
            card.rev += 1
            card.save(update_fields=["needs_recheck", "recheck_reason", "recheck_ref", "rev", "updated_at"])
        return RecallCard.objects.select_related("item", "item_version").get(pk=card.pk)


def _unsuspend(card: RecallCard, now: datetime) -> None:
    if card.status != "suspended":
        return
    card.status, card.suspend_reason = "active", None
    card.rev += 1
    card.save(update_fields=["status", "suspend_reason", "rev", "updated_at"])
    RecallScheduleEvent.objects.create(user_id=card.user_id, card=card, kind="unsuspend", at=now, reason_code="student")


def _bury(user_id, card: RecallCard, now: datetime, until: datetime | None) -> None:
    if until is None:
        tz, day_start = student.study_clock(user_id)
        until = scheduling.end_of_study_day(now, tz, day_start)
    elif until <= now or until > now + timedelta(days=BURY_MAX_DAYS):
        _refuse([_issue("until", "bad_until", f"Bury until a time within the next {BURY_MAX_DAYS} days.")])
    card.buried_until = until
    card.rev += 1
    card.save(update_fields=["buried_until", "rev", "updated_at"])


def _reset(card: RecallCard, now: datetime) -> None:
    RecallScheduleEvent.objects.create(
        user_id=card.user_id,
        card=card,
        kind="forget",
        at=now,
        from_due=card.due_at,
        stability_before=card.stability,
        reason_code="student",
    )
    card.state, card.step = 0, None
    card.stability = card.difficulty = card.due_scheduled_at = card.due_at = None
    card.postponed_until = card.last_review_at = card.last_lapse_at = card.buried_until = None
    card.reps = card.lapses = 0
    card.leech = False
    card.rev += 1
    card.save()


# --------------------------------------------------------------------------------------------------- undo
def undo_delete(user_id, token: str) -> RecallCard:
    """Restore an item deleted less than 10 seconds ago and re-reserve its quota (429 when the plan filled up meanwhile)."""
    payload = _unsign(user_id, token)
    if payload.get("a") != "delete":
        raise NotFound("Not found.")
    with transaction.atomic():
        card = (
            RecallCard.objects.select_for_update(of=("self",))
            .select_related("item", "item_version")
            .filter(pk=payload["c"], user_id=user_id)
            .first()
        )
        if card is None:
            raise NotFound("Card not found.")
        item = card.item
        if item.status != "deleted":  # already restored: the undo is idempotent
            return card
        faces = list(RecallCard.objects.filter(item=item, user_id=user_id, status="deleted"))
        decks = _deck_ids_of(item)
        quota.reserve_cards(user_id, len(faces))
        for deck_id in decks:
            quota.reserve_deck_member(user_id, deck_id, len(faces))
        item.status, item.deleted_at = "active", None
        item.save(update_fields=["status", "deleted_at", "updated_at"])
        for face in faces:
            face.status = "suspended" if face.suspend_reason else "active"
            face.deleted_at = None
            face.rev += 1
            face.save(update_fields=["status", "deleted_at", "rev", "updated_at"])
        return RecallCard.objects.select_related("item", "item_version").get(pk=card.pk)


def undo_create(user_id, token: str) -> RecallCard:
    """Delete a card created less than 10 seconds ago (the token a selection card came with)."""
    payload = _unsign(user_id, token)
    if payload.get("a") != "create":
        raise NotFound("Not found.")
    card, _ = set_card_status(user_id, payload["c"], "delete")
    return card


def undo(user_id, token: str) -> RecallCard:
    """One entry point for either token kind (`cards/undo-delete/`)."""
    action = _unsign(user_id, token).get("a")
    return undo_create(user_id, token) if action == "create" else undo_delete(user_id, token)


# --------------------------------------------------------------------------------------------------- bulk
def bulk_update(user_id, ids: Sequence[UUID], action: str, **args: Any) -> BulkResult:
    """Up to 200 cards, all or none: one transaction, and any id that is not the student's (or is deleted) aborts it with 404."""
    unique = list(dict.fromkeys(ids))
    if len(unique) > BULK_MAX:
        raise BulkTooLarge
    if action not in BULK_ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    with transaction.atomic():
        cards = _lock_cards(user_id, unique)
        items = _items_of(cards)
        now = _now()
        if action == "move_chapter":
            _apply_link(items, syllabus_adapter.link_columns(args.get("chapter_id"), args.get("topic_id")), now)
        elif action == "set_importance":
            _apply_importance(items, clean_importance(args.get("importance", "")), now)
        elif action == "add_tag":
            _apply_tags(items, clean_tags([args.get("tag")]), now, add=True)
        elif action == "suspend":
            _suspend(cards, now)
        elif action == "delete":
            _delete_items(user_id, items, now)
        else:
            _add_to_deck(user_id, items, args["deck_id"], now)
        if action in ("move_chapter", "set_importance", "add_tag"):
            _bump(items, now)
        return BulkResult(len(unique), tuple(unique))
