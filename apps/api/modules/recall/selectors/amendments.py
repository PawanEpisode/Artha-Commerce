"""Amendment reads (R2-W2): which platform items carry the "Under review after amendment" ribbon. Ids only, no text."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from ..models import RecallAmendmentFlag


def under_review_item_ids(item_ids: Iterable[UUID]) -> set[UUID]:
    """Of these items, the ones with at least one amendment flag."""
    ids = list(item_ids)
    if not ids:
        return set()
    return set(RecallAmendmentFlag.objects.filter(item_id__in=ids).values_list("item_id", flat=True))
