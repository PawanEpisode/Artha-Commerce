"""
Plan limits and the arithmetic around them (PRD 8.5, ERD 2.11). Pure: the database side (atomic conditional updates) is in
`services.quota`. Limits are data (`notes_quotaplan`); `FREE` is the fallback and the seed, so a missing row never means
"unlimited".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MB = 1024 * 1024


@dataclass(frozen=True)
class Limits:
    max_storage_mb: int
    max_file_mb: int
    max_pages: int
    max_documents: int
    max_notes: int
    max_note_chars: int
    max_note_images: int
    max_marks_per_document: int
    max_tags: int
    ocr_pages_per_month: int
    ai_ocr_pages_per_month: int
    ai_summaries_per_month: int
    exports_per_month: int
    max_share_links: int
    max_offline_documents: int

    @property
    def storage_bytes(self) -> int:
        return self.max_storage_mb * MB

    @property
    def file_bytes(self) -> int:
        return self.max_file_mb * MB

    def as_dict(self) -> dict[str, int]:
        return asdict(self)

    @classmethod
    def names(cls) -> list[str]:
        return [f.name for f in fields(cls)]


FREE = Limits(
    max_storage_mb=500,
    max_file_mb=50,
    max_pages=1000,
    max_documents=100,
    max_notes=2000,
    max_note_chars=100_000,
    max_note_images=40,
    max_marks_per_document=20_000,
    max_tags=200,
    ocr_pages_per_month=300,
    ai_ocr_pages_per_month=0,
    ai_summaries_per_month=5,
    exports_per_month=10,
    max_share_links=20,
    max_offline_documents=3,
)


def fits(used: int, add: int, limit: int) -> bool:
    """True when `add` more still fits under `limit`. The same inequality the conditional UPDATE writes in SQL."""
    return used + add <= limit


def month_start(now: datetime) -> date:
    """First day of the month in India time: the key of the monthly counters, so they reset at midnight in Delhi."""
    local = now.astimezone(IST)
    return date(local.year, local.month, 1)


def resets_on(now: datetime) -> date:
    start = month_start(now)
    return date(start.year + (start.month == 12), start.month % 12 + 1, 1)
