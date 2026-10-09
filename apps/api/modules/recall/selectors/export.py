"""
Streamed CSV of her cards and reviews (FR-F15-75). Rows come from the database in keyset chunks, so memory stays flat and the
file is never silently cut: the last line says `#complete,<rows>`, or `#next,<cursor>` when the caller asked for a page with
`limit` and there is more (send the cursor back to continue). Platform cards are listed without their text (the platform's
words are not exported in bulk); her own cards carry their fields as JSON. Cells that a spreadsheet would run as a formula are
prefixed with an apostrophe.
"""

from __future__ import annotations

import base64
import csv
import io
import json
from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

from django.db.models import Q

from ..errors import BadCursor
from ..models import RecallCard, RecallReviewLog

CHUNK = 2000
MAX_PAGE = 100_000
CARD_HEADER = (
    "card_id", "item_id", "ordinal", "source", "kind", "importance", "status", "state", "step", "stability", "difficulty",
    "due_at", "last_review_at", "reps", "lapses", "leech", "chapter_key", "subject_key", "tags", "created_at", "fields_json",
)  # fmt: skip
REVIEW_HEADER = (
    "review_id", "kind", "card_id", "item_id", "session_id", "rating", "reviewed_at", "duration_ms", "mode",
    "counts_for_scheduling", "device_id", "local_date", "voids_id", "flags",
)  # fmt: skip
_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value) -> str:
    if value is None:
        return ""
    text = value.isoformat() if isinstance(value, datetime) else str(value)
    return "'" + text if text.startswith(_DANGEROUS) else text


def _line(values) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\r\n").writerow([safe_cell(v) for v in values])
    return buffer.getvalue()


def encode_cursor(at: datetime, pk: UUID) -> str:
    return base64.urlsafe_b64encode(json.dumps([at.isoformat(), str(pk)]).encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = json.loads(base64.urlsafe_b64decode((cursor + "=" * (-len(cursor) % 4)).encode()))
        return datetime.fromisoformat(raw[0]), UUID(raw[1])
    except (ValueError, TypeError, IndexError, UnicodeDecodeError) as exc:
        raise BadCursor from exc


def _keyset(qs, column: str, at: datetime, last: UUID):
    return qs.filter(Q(**{f"{column}__gt": at}) | Q(**{column: at, "id__gt": last}))


def _stream(header, qs, column: str, make_row, *, cursor: str | None, limit: int | None) -> Iterator[str]:
    """Header, then rows in keyset chunks, then one footer line. A bad cursor raises now, before any byte is sent."""
    start = decode_cursor(cursor) if cursor else None
    return _chunks(header, qs, column, make_row, start, limit)


def _chunks(header, qs, column: str, make_row, start, limit: int | None) -> Iterator[str]:
    yield _line(header)
    base = qs.order_by(column, "id")
    last: tuple[datetime, UUID] | None = start
    sent = 0
    while limit is None or sent < limit:
        want = CHUNK if limit is None else min(CHUNK, limit - sent)
        page = base if last is None else _keyset(base, column, *last)
        rows = list(page[:want])
        for obj in rows:
            yield _line(make_row(obj))
        sent += len(rows)
        if rows:
            last = (getattr(rows[-1], column), rows[-1].id)
        if len(rows) < want:
            yield _line(["#complete", sent])
            return
    more = last is not None and _keyset(base, column, *last).exists()
    yield _line(["#next", encode_cursor(*last)] if more and last else ["#complete", sent])


def cards_csv(user_id, *, cursor: str | None = None, limit: int | None = None) -> Iterator[str]:
    qs = RecallCard.objects.filter(user_id=user_id).select_related("item", "item_version")

    def make(c: RecallCard):
        own = c.item.ownership == "user"
        fields = (
            json.dumps({k: v for k, v in c.item_version.fields.items() if k != "v"}, ensure_ascii=False) if own else ""
        )
        return (
            c.id, c.item_id, c.ordinal, "own" if own else "platform", c.item.kind, c.item.importance, c.status, c.state,
            c.step, c.stability, c.difficulty, c.due_at, c.last_review_at, c.reps, c.lapses, c.leech, c.item.chapter_key,
            c.item.subject_key, ";".join(c.item.tags), c.created_at, fields,
        )  # fmt: skip

    return _stream(CARD_HEADER, qs, "created_at", make, cursor=cursor, limit=limit)


def reviews_csv(user_id, *, cursor: str | None = None, limit: int | None = None) -> Iterator[str]:
    qs = RecallReviewLog.objects.filter(user_id=user_id)

    def make(r: RecallReviewLog):
        return (
            r.id, r.kind, r.card_id, r.item_id, r.session_id, r.rating, r.reviewed_at, r.duration_ms, r.mode,
            r.counts_for_scheduling, r.device_id, r.local_date, r.voids_id, ";".join(r.flags),
        )  # fmt: skip

    return _stream(REVIEW_HEADER, qs, "reviewed_at", make, cursor=cursor, limit=limit)
