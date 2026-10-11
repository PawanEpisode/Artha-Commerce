"""
Paste and CSV import (FR-F13, R2-W3 F). One function judges the rows (`check`, used by the preview and the real call, so they
cannot disagree) and one writes them (`run`).

- The preview (`dry_run`) writes nothing and says, per row, what is wrong, plus whether the valid rows fit her plan.
- The real call creates only the valid rows, in ONE transaction with ONE quota reservation for all their faces
  (`quota.reserve_cards(total)`): when the plan cannot hold them all, 429 `quota_exceeded` and nothing is created.
- Each row has its own client id derived from the batch id and its line (uuid5), so a replay of the same batch finds its cards
  and creates nothing twice (those rows come back as `existing`).
- Duplicates (a card she already has, or the same row twice in the batch) are row errors; the import never forces.
- Privacy: the results carry line numbers, codes and ids. No card text is logged or echoed.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import UUID

from django.db import transaction

from .. import registry
from ..adapters import coverage as coverage_adapter
from ..adapters import syllabus as syllabus_adapter
from ..domain import cards as card_rules
from ..domain import imports as parse
from ..errors import BulkTooLarge, InvalidFields, UnknownKind
from ..models import RecallItem
from . import cards as card_services
from . import quota

logger = logging.getLogger(__name__)

NAMESPACE = uuid.UUID("5d4f7a64-7a5e-4f36-b1c0-3f5b0d5a9e11")
ORIGIN = "import_csv"


class ImportTooLarge(BulkTooLarge):
    default_detail = f"An import takes at most {parse.ROW_LIMIT} rows."
    default_code = "import_too_large"


@dataclass
class RowResult:
    line: int
    status: str = "ok"  # ok (valid), error, created, existing
    kind: str | None = None
    issues: list[dict] = field(default_factory=list)
    card_id: UUID | None = None
    front: str = ""  # a short excerpt, so the preview table can show the row next to its error
    back: str = ""
    # internal, never serialised
    fields: dict = field(default_factory=dict)
    chapter_id: UUID | None = None
    faces: int = 0
    client_id: UUID | None = None
    fingerprint: str = ""


@dataclass
class ImportOutcome:
    dry_run: bool
    rows: list[RowResult]
    room: int
    needed: int

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def valid(self) -> int:
        return sum(1 for r in self.rows if r.status in ("ok", "created"))

    @property
    def invalid(self) -> int:
        return sum(1 for r in self.rows if r.status == "error")

    @property
    def created(self) -> int:
        return sum(1 for r in self.rows if r.status == "created")

    @property
    def existing(self) -> int:
        return sum(1 for r in self.rows if r.status == "existing")


def _issue(field_name: str, code: str, message: str) -> dict:
    return {"field": field_name, "code": code, "message": message}


EXCERPT_CHARS = 120


def _excerpt(text: str) -> str:
    one = " ".join(text.split())
    return one if len(one) <= EXCERPT_CHARS else one[: EXCERPT_CHARS - 1].rstrip() + "…"


def client_id_for(batch_id: UUID, line: int) -> UUID:
    return uuid.uuid5(NAMESPACE, f"{batch_id}:{line}")


def parse_input(*, text: str | None, rows: Sequence[dict] | None) -> list[parse.RawRow]:
    raw = parse.parse_text(text) if text is not None else parse.from_rows(rows or [])
    if len(raw) > parse.ROW_LIMIT:
        raise ImportTooLarge
    return raw


def _chapter_lookup(user_id, raw: Sequence[parse.RawRow]) -> dict[str, UUID]:
    """Chapter cells to ids: an id, `subject/chapter` or a bare chapter key, within her current scheme. One query, only if needed."""
    cells = {r.chapter for r in raw if r.chapter}
    if not cells:
        return {}
    scheme_id = coverage_adapter.active_scheme_id(user_id)
    found: dict[str, UUID] = {}
    if scheme_id is None:
        return found
    chapters = syllabus_adapter.chapters_of_scheme(scheme_id)
    by_key: dict[str, list[UUID]] = {}
    for c in chapters:
        found[str(c.id)] = c.id
        found[f"{c.subject_key}/{c.key}".lower()] = c.id
        by_key.setdefault(c.key.lower(), []).append(c.id)
    for key, ids in by_key.items():
        if len(ids) == 1:
            found.setdefault(key, ids[0])  # a bare key works only when it names one chapter
    return {cell: found[cell.lower()] for cell in cells if cell.lower() in found}


def check(user_id, raw: Sequence[parse.RawRow], *, batch_id: UUID, chapter_id: UUID | None = None) -> list[RowResult]:
    """Judge every row. Pure reads (a few queries for the whole batch, never one per row)."""
    chapters = _chapter_lookup(user_id, raw)
    default_link = (
        syllabus_adapter.link_columns(chapter_id) if chapter_id else None
    )  # 422 unknown_chapter for the batch
    prior = set(
        RecallItem.objects.filter(
            owner_user_id=user_id, client_id__in=[client_id_for(batch_id, r.line) for r in raw]
        ).values_list("client_id", flat=True)
    )
    out: list[RowResult] = []
    for row in raw:
        res = RowResult(
            row.line,
            kind=row.kind or None,
            front=_excerpt(row.front),
            back=_excerpt(row.back),
            client_id=client_id_for(batch_id, row.line),
        )
        out.append(res)
        if res.client_id in prior:
            res.status = "existing"  # the same batch again: its cards are already there
            continue
        _judge(res, row, chapters, chapter_id if default_link else None)
    _mark_duplicates(user_id, out)
    return out


def _judge(res: RowResult, row: parse.RawRow, chapters: dict[str, UUID], default_chapter: UUID | None) -> None:
    if row.error:
        res.issues.append(_issue("row", row.error, "This line could not be read."))
        res.status = "error"
        return
    try:
        spec = registry.get_kind(row.kind)
    except UnknownKind:
        res.issues.append(_issue("kind", "unknown_kind", "Unknown card kind."))
        res.status = "error"
        return
    required = [f.name for f in spec.fields if f.required]
    if not parse.importable_fields(required):
        res.issues.append(_issue("kind", "kind_needs_form", "This kind has more fields than an import can fill."))
        res.status = "error"
        return
    if len(required) == 1 and row.back:
        res.issues.append(_issue("back", "back_not_used", "This kind has no back. Leave it empty."))
    res.chapter_id = default_chapter
    if row.chapter:
        res.chapter_id = chapters.get(row.chapter)
        if res.chapter_id is None:
            res.issues.append(_issue("chapter", "unknown_chapter", "That chapter is not in your syllabus."))
    if res.issues:
        res.status = "error"
        return
    fields = card_services.clean_fields(spec, parse.map_fields(required, row))
    try:
        card_services.check_fields(spec, fields)
    except InvalidFields as exc:
        res.issues.extend(_issue(e["field"], e["code"], e["message"]) for e in (exc.extra or {}).get("errors", []))
        res.status = "error"
        return
    res.fields = fields
    res.faces = len(spec.ordinals(fields))
    res.fingerprint = card_rules.fingerprint(row.kind, fields)


def _mark_duplicates(user_id, results: list[RowResult]) -> None:
    candidates = [r for r in results if r.status == "ok"]
    if not candidates:
        return
    have = set(
        RecallItem.objects.filter(
            owner_user_id=user_id,
            ownership="user",
            status__in=["active", "archived"],
            fingerprint__in=[r.fingerprint for r in candidates],
        ).values_list("fingerprint", flat=True)
    )
    seen: set[str] = set()
    for r in candidates:
        if r.fingerprint in have:
            r.status = "error"
            r.issues.append(_issue("row", "duplicate_card", "You already have this card."))
        elif r.fingerprint in seen:
            r.status = "error"
            r.issues.append(_issue("row", "duplicate_in_import", "This row repeats an earlier row."))
        seen.add(r.fingerprint)


def run(
    user_id,
    raw: Sequence[parse.RawRow],
    *,
    batch_id: UUID,
    dry_run: bool,
    chapter_id: UUID | None = None,
    importance: str = "bullet",
) -> ImportOutcome:
    """The preview or the real import. See the module docstring for the guarantees."""
    card_services.clean_importance(importance)
    with transaction.atomic():
        results = check(user_id, raw, batch_id=batch_id, chapter_id=chapter_id)
        valid = [r for r in results if r.status == "ok"]
        needed = sum(r.faces for r in valid)
        outcome = ImportOutcome(dry_run, results, quota.cards_room(user_id), needed)
        if dry_run or not valid:
            return outcome
        quota.reserve_cards(user_id, needed)  # one conditional UPDATE for all of them: all or nothing
        by_line = {r.line: r for r in raw}
        for res in valid:
            row = by_line[res.line]
            created = card_services.create_card(
                user_id,
                kind=row.kind,
                fields=res.fields,
                chapter_id=res.chapter_id,
                importance=importance,
                client_id=res.client_id,
                origin=ORIGIN,
                reserve_quota=False,
            )
            res.status, res.card_id = "created", created.card_id
    logger.info("recall import rows=%d created=%d invalid=%d", len(results), outcome.created, outcome.invalid)
    return outcome
