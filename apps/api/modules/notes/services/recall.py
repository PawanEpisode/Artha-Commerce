"""
"Make a card" from a mark (slice 19, FR-F03-55/56). Notes never imports the recall module: it asks the provider registered in
`core.recall_port`, so this works the day F-15 registers one and answers 503 until then.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from rest_framework.exceptions import NotFound

from core.recall_port import CardRef, SourceRef, get_recall_provider
from modules.syllabus import selectors as syllabus

from ..domain import recall_card
from ..domain.legend import default_legend
from ..errors import NoText, RecallUnavailable
from ..models import Annotation, Note, Settings
from . import annotations


@dataclass(frozen=True)
class CardResult:
    card_id: UUID
    existing: bool


def create_recall_card(
    user_id, *, item_type: str, item_id: UUID, kind: str | None = None, client_id: UUID
) -> CardResult:
    """
    One card per mark and kind. The back is the mark's quote (and comment), the front an auto prompt from the chapter and the
    colour's meaning in the student's legend; the kind follows that meaning unless the student picked one. A second call
    returns the same card with `existing` true: the provider is idempotent on `(student, mark, kind)` and the id is cached
    on the mark. `NotFound` for a mark that is not the student's, `RecallUnavailable` without a provider, `NoText` for a mark
    with neither quote nor comment.
    """
    if item_type == "annotation":
        item = Annotation.objects.filter(pk=item_id, user_id=user_id, deleted_at__isnull=True).first()
    elif item_type == "note":
        item = Note.objects.filter(pk=item_id, user_id=user_id, deleted_at__isnull=True).first()
    else:
        raise ValueError(f"unknown item type {item_type!r}")
    if item is None:
        raise NotFound("Not found.")
    provider = get_recall_provider()
    if provider is None:
        raise RecallUnavailable
    cached = getattr(item, "recall_card_id", None)
    if cached and kind is None:
        return CardResult(cached, True)
    if item_type == "note":
        return _from_note(provider, user_id, item, kind, client_id)
    return _from_mark(provider, user_id, item, kind, client_id)


def _legend_of(user_id) -> dict[str, str]:
    legend = Settings.objects.filter(pk=user_id).values_list("color_legend", flat=True).first()
    return legend or default_legend()


def _chapter_of(item) -> tuple[UUID | None, UUID | None, str | None]:
    """The chapter in the level's current scheme (ids change with a scheme switch, keys do not), else the stored one."""
    if not item.chapter_id:
        return None, None, None
    ref = syllabus.resolve_keys(item.level_id, item.subject_key, item.chapter_key) or syllabus.chapter_refs(
        [item.chapter_id]
    ).get(item.chapter_id)
    return (ref.id, item.topic_id, ref.name) if ref else (item.chapter_id, item.topic_id, None)


def _from_mark(provider, user_id, mark: Annotation, kind: str | None, client_id: UUID) -> CardResult:
    back = recall_card.back_text(mark.quote_exact, mark.comment)
    if not back:
        raise NoText
    chosen = kind or recall_card.card_kind_for_color(mark.color, _legend_of(user_id))
    chapter_id, topic_id, chapter_name = _chapter_of(mark)
    card = provider.create_card_from_source(
        user_id,
        kind=chosen,
        front_md=recall_card.front_prompt(chosen, chapter_name=chapter_name, page=mark.page),
        back_md=back,
        chapter_id=chapter_id,
        topic_id=topic_id,
        source=SourceRef("notes", "annotation", mark.id),
        client_id=client_id,
    )
    if mark.recall_card_id is None:
        annotations.remember_recall_card(user_id, mark.id, card.id)
    return CardResult(card.id, card.existing)


def _from_note(provider, user_id, note: Note, kind: str | None, client_id: UUID) -> CardResult:
    back = (note.body_md or "").strip()
    if not back:
        raise NoText
    chosen = kind or "fact"
    chapter_id, topic_id, chapter_name = _chapter_of(note)
    card: CardRef = provider.create_card_from_source(
        user_id,
        kind=chosen,
        front_md=note.title.strip() or f"Recall this note from {chapter_name or 'your notes'}.",
        back_md=back,
        chapter_id=chapter_id,
        topic_id=topic_id,
        source=SourceRef("notes", "note", note.id),
        client_id=client_id,
    )
    return CardResult(card.id, card.existing)
