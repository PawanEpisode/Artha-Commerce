"""
"This pointer is wrong or outdated" (FR-F15-52). A student reports a PLATFORM item; the report reaches editors in the Django
admin with the item version she saw. One open report per student and item, so a second tap is a no-op. The note is free text:
it is stored, never logged and never sent to analytics.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.db import IntegrityError, transaction

from ..errors import CodedError
from ..models import REPORT_REASONS, RecallCard, RecallDeckVersionItem, RecallItem, RecallReport

NOTE_MAX = 500


class ItemNotReportable(CodedError):
    """404: a student can report only a live platform item that she can see (it is in a live deck, or she has its card)."""

    status_code = 404
    default_detail = "That item was not found."
    default_code = "item_not_found"


@dataclass(frozen=True)
class ReportResult:
    report: RecallReport
    created: bool


def _visible_item(user_id, item_id: UUID) -> RecallItem:
    item = RecallItem.objects.filter(
        pk=item_id, ownership="platform", status="active", deleted_at__isnull=True, live_version__isnull=False
    ).first()
    if item is None:
        raise ItemNotReportable
    in_live_deck = RecallDeckVersionItem.objects.filter(
        item=item, deck_version__state="live", deck_version__deck__status="active"
    ).exists()
    if not in_live_deck and not RecallCard.objects.filter(user_id=user_id, item=item).exists():
        raise ItemNotReportable
    return item


def report_item(user_id, item_id: UUID, *, reason: str, note: str = "") -> ReportResult:
    if reason not in REPORT_REASONS:
        raise ValueError(reason)
    item = _visible_item(user_id, item_id)
    # The version she saw: the one on her card, else the live one.
    seen = RecallCard.objects.filter(user_id=user_id, item=item).values_list("item_version_id", flat=True).first()
    existing = RecallReport.objects.filter(
        reporter_user_id=user_id, target_kind="item", target_id=item.id, status="open"
    ).first()
    if existing is not None:
        return ReportResult(existing, False)
    try:
        with transaction.atomic():
            report = RecallReport.objects.create(
                target_kind="item",
                target_id=item.id,
                item_version_id=seen or item.live_version_id,
                reporter_user_id=user_id,
                reason=reason,
                note=note.strip()[:NOTE_MAX],
            )
    except IntegrityError:  # a double tap raced us: the unique open report wins
        report = RecallReport.objects.get(
            reporter_user_id=user_id, target_kind="item", target_id=item.id, status="open"
        )
        return ReportResult(report, False)
    return ReportResult(report, True)
