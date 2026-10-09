"""
The recall provider Notes uses through `core.recall_port` (D2). Notes never imports this module; `RecallConfig.ready` registers
it. The port does not know the `recall_system` flag, so registering a provider would switch Notes' "Make a card" on for every
student: both methods therefore check the flag for that student and behave as "no recall" (`RecallUnavailable`, `{}`) when it is
off. The flag lookup never raises.

Port kind to card kind (D2): formula -> formula, definition -> definition, rule / example / doubt / fact -> pointer. The port kind
itself is kept in `recall_item.origin_kind`, and a partial unique index on (student, module, source id, port kind) makes the
call idempotent, race-safe through the database. Created cards are never shareable.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from uuid import UUID

from core import richtext
from core.feature_flags import flag_enabled
from core.recall_port import CARD_KINDS, CardRef, RecallUnavailable, SourceRef

from . import selectors
from .domain.limits import FIELD_MAX_CHARS
from .errors import InvalidFields
from .permissions import RECALL_FLAG
from .services import cards as card_services

logger = logging.getLogger(__name__)

CARD_KIND_OF = {
    "formula": "formula",
    "definition": "definition",
    "rule": "pointer",
    "example": "pointer",
    "doubt": "pointer",
    "fact": "pointer",
}
TITLE_MAX = 120


def _title(front_md: str, fallback: str) -> str:
    line = " ".join(richtext.plain_text(front_md).split("\n", 1)[0].split()).strip(" :.-")
    line = line if len(line) <= TITLE_MAX else line[: TITLE_MAX - 1].rstrip() + "…"
    return line or fallback


def fields_for_port_kind(port_kind: str, front_md: str, back_md: str) -> tuple[str, dict]:
    """`(card kind, fields)` for a port kind. Pure. Text is trimmed to the field limits, never rejected for length."""
    kind = CARD_KIND_OF[port_kind]
    front, back = front_md.strip(), back_md.strip()
    long = FIELD_MAX_CHARS
    if kind == "formula":
        return kind, {"name": _title(front, "Formula"), "expression_md": back[:long]}
    if kind == "definition":
        return kind, {"term": _title(front, "Definition"), "definition_md": back[:long]}
    return kind, {"prompt_md": (front or "Recall this point.")[:long], "answer_md": back[:long]}


def _enabled(user_id) -> bool:
    try:
        return flag_enabled(RECALL_FLAG, user_id, strict=True)
    except Exception:  # noqa: BLE001 - the flag lookup must never break Notes
        logger.warning("recall flag lookup failed", exc_info=True)
        return False


class RecallProviderImpl:
    def available_for(self, user_id) -> bool:
        """Notes' `capabilities.recall`: on only for students whose `recall_system` flag is on."""
        return _enabled(user_id)

    def create_card_from_source(
        self,
        user_id,
        *,
        kind: str,
        front_md: str,
        back_md: str,
        chapter_id: UUID | None = None,
        topic_id: UUID | None = None,
        source: SourceRef,
        client_id: UUID,
    ) -> CardRef:
        if not _enabled(user_id):
            raise RecallUnavailable
        if kind not in CARD_KINDS:
            raise ValueError(f"unknown port kind {kind!r}")
        if source.module not in card_services.ORIGIN_MODULES:
            raise ValueError(f"unsupported source module {source.module!r}")

        def make(front: str, back: str):
            card_kind, fields = fields_for_port_kind(kind, front, back)
            return card_services.create_card(
                user_id,
                kind=card_kind,
                fields=fields,
                chapter_id=chapter_id,
                topic_id=topic_id,
                client_id=client_id,
                force=True,  # two marks with the same words are still two sources
                origin="selection",
                source=source,
                origin_kind=kind,
                origin_locator={"ref_type": source.ref_type},
                shareable=False,
            )

        try:
            result = make(front_md, back_md)
        except (
            InvalidFields
        ):  # a quote can carry Markdown the card profile refuses (headings, images): fall back to plain text
            result = make(richtext.plain_text(front_md), richtext.plain_text(back_md))
        return CardRef(result.card_id, result.existing)

    def cards_for_source(self, user_id, ref_ids: Sequence[UUID]) -> Mapping[UUID, CardRef]:
        if not ref_ids or not _enabled(user_id):
            return {}
        return {ref: CardRef(card_id) for ref, card_id in selectors.cards_for_source(user_id, None, ref_ids).items()}
