"""
A card from a mistake (FR-F15-17, R2-W4): she got a question wrong and taps "Make a card". The text comes from the question
bank (F-06) through `core.question_port`: its explanation and the labels of the source it cites, never from a model. Idempotent
per question (the unique source key `questionbank / question id / question_mistake`), so a second tap, another device or a replay
returns the card she already has. The card is private (`shareable = false`) until she says the words are her own (FR-F15-21).
Nothing here logs card text.
"""

from __future__ import annotations

from uuid import UUID

from rest_framework.exceptions import NotFound

from core import question_port
from core.recall_port import SourceRef

from ..domain import question_card
from ..errors import DuplicateCard, QuestionHasNoSource, UnknownChapter
from ..models import RecallItem
from . import cards

ORIGIN_KIND = "question_mistake"  # at most 16 characters (the column)
MODULE = "questionbank"
IMPORTANCE = "bullet"


def create_card_from_question(
    user_id,
    *,
    question_id: UUID,
    version_id: UUID,
    chapter_id: UUID | None = None,
    client_id: UUID | None = None,
    force: bool = False,
) -> cards.CreatedCards:
    """
    503 `question_source_unavailable` with no question bank, 404 when it does not know the question for her, 422
    `question_has_no_source` when it has nothing to quote. `chapter_id` overrides the chapter the bank puts the question in;
    when the bank's own chapter is not in her scheme the card is made Unsorted rather than refused.
    """
    provider = question_port.get_question_provider()
    if provider is None:
        raise question_port.QuestionSourceUnavailable
    source = provider.source_for(user_id, question_id, version_id)
    if source is None:
        raise NotFound("Question not found.")
    fields = question_card.build_fields(source.explanation_md, source.reference_labels, source.source_label)
    if fields is None:
        raise QuestionHasNoSource
    ref = SourceRef(module=MODULE, ref_type="question", ref_id=question_id)
    explicit = chapter_id is not None
    wanted = chapter_id or source.chapter_id
    topic = None if explicit else source.topic_id

    def make(chapter, topic_id):
        return cards.create_card(
            user_id,
            kind="pointer",
            fields=fields,
            chapter_id=chapter,
            topic_id=topic_id,
            importance=IMPORTANCE,
            reference_keys=source.reference_keys,
            client_id=client_id,
            force=force,
            origin="mistake",
            source=ref,
            origin_kind=ORIGIN_KIND,
            origin_locator={"version_id": str(version_id)},
            shareable=False,
        )

    try:
        try:
            result = make(wanted, topic)
        except UnknownChapter:
            if explicit:
                raise
            result = make(None, None)  # the bank's chapter is from another scheme: keep the card, leave it Unsorted
    except DuplicateCard as dup:
        item_id = (dup.extra or {}).get("item_id")
        item = RecallItem.objects.filter(pk=item_id, owner_user_id=user_id).first() if item_id else None
        if item is None or item.origin_ref != str(question_id):
            raise
        result = cards.CreatedCards(item, cards._cards_of(item), existing=True)
    if not result.existing:
        result.undo_token = cards._sign("create", result.card_id, user_id)
    return result
