from __future__ import annotations

import base64
from datetime import datetime

from django.db.models import Q, QuerySet
from django.utils import timezone

from ..domain.catalogue import CATEGORIES, is_enabled
from ..domain.enums import Channel, SuppressReason
from ..errors import InvalidCursor
from ..models import Notification
from .preferences import overrides

#: The inbox shows the last 50 notifications (PRD FR-N8); older ones are kept only until retention prunes them.
INBOX_CAP = 50
DEFAULT_PAGE = 20


def hidden_categories(user_id) -> list[str]:
    """Categories whose inbox switch the student turned off. The test push (system) has no switch and always shows."""
    chosen = overrides(user_id)
    return [spec.key.value for spec in CATEGORIES if not is_enabled(spec.key.value, Channel.INBOX.value, chosen)]


def visible(user_id, *, now: datetime | None = None) -> QuerySet[Notification]:
    """
    The student's own notifications that may show: not expired, not in a category switched off for the inbox, and not a
    nudge that was never sent because the student had already opened the app that day (they have seen the thought).
    """
    now = now or timezone.now()
    return (
        Notification.objects.filter(user_id=user_id)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .exclude(category__in=hidden_categories(user_id))
        .exclude(deliveries__suppress_reason=SuppressReason.VISITED_TODAY)
    )


def unread_count(user_id, *, now: datetime | None = None) -> int:
    return visible(user_id, now=now).filter(read_at__isnull=True).count()


def _encode_cursor(row: Notification, seen: int) -> str:
    return base64.urlsafe_b64encode(f"{row.created_at.isoformat()}|{row.id}|{seen}".encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str, int]:
    try:
        created, pk, seen = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(created), pk, int(seen)
    except (ValueError, UnicodeError):
        raise InvalidCursor from None


def list_inbox(
    user_id, *, cursor: str | None = None, limit: int = DEFAULT_PAGE, now: datetime | None = None
) -> tuple[list[Notification], str | None]:
    """
    Newest first, keyset paged, and never past the newest `INBOX_CAP` visible rows. Returns the rows and the cursor of
    the next page (None at the end). The cursor carries how many rows were already served so the cap holds across pages.
    """
    limit = max(1, min(limit, INBOX_CAP))
    rows = visible(user_id, now=now).order_by("-created_at", "-id")
    seen = 0
    if cursor:
        created, pk, seen = _decode_cursor(cursor)
        if seen < 0 or seen >= INBOX_CAP:
            raise InvalidCursor
        rows = rows.filter(Q(created_at__lt=created) | Q(created_at=created, id__lt=pk))
    take = min(limit, INBOX_CAP - seen)
    page = list(rows[: take + 1])
    more = len(page) > take and seen + take < INBOX_CAP
    page = page[:take]
    return page, (_encode_cursor(page[-1], seen + len(page)) if more and page else None)
