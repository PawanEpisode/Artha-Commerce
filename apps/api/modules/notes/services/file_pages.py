"""
Writes of derived page text (ERD 2.3, 6.5), shared by the extract job (native text) and the OCR job. One rule decides who wins
a page: `native < ocr < ai`. A write never replaces text of a higher rank (re-extracting a file that was OCR'd later must not
throw the OCR away), and a write of the same rank replaces (a re-run refreshes). Language and the stored search vector are set
afterwards by `search_index.refresh_pages`, which the caller runs for the pages it wrote.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from django.db import connection
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from ..models import FileContent, FilePage

SOURCE_RANK = {"native": 0, "ocr": 1, "ai": 2}


@dataclass(frozen=True)
class PageWrite:
    page: int
    text: str
    source: str = "native"
    conf: int | None = None
    words: list | None = None


_UPSERT = """
INSERT INTO notes_filepage (content_id, page, text, text_source, ocr_conf, words, words_schema, lang, created_at, updated_at)
VALUES {values}
ON CONFLICT (content_id, page) DO UPDATE SET
    text = EXCLUDED.text, text_source = EXCLUDED.text_source, ocr_conf = EXCLUDED.ocr_conf,
    words = EXCLUDED.words, updated_at = EXCLUDED.updated_at
WHERE (CASE EXCLUDED.text_source WHEN 'native' THEN 0 WHEN 'ocr' THEN 1 ELSE 2 END)
   >= (CASE notes_filepage.text_source WHEN 'native' THEN 0 WHEN 'ocr' THEN 1 ELSE 2 END)
"""


def upsert_pages(content_id, pages: Sequence[PageWrite], *, now: datetime | None = None) -> int:
    """Stores the pages under the rank rule. Returns how many rows were written (inserted or replaced)."""
    if not pages:
        return 0
    now = now or timezone.now()
    if connection.vendor == "postgresql":
        return _upsert_sql(content_id, pages, now)
    written = 0
    for p in pages:  # SQLite (quick tests): same rule, row by row
        existing = FilePage.objects.filter(content_id=content_id, page=p.page).first()
        if existing is not None and SOURCE_RANK[existing.text_source] > SOURCE_RANK[p.source]:
            continue
        FilePage.objects.update_or_create(
            content_id=content_id,
            page=p.page,
            defaults={"text": p.text, "text_source": p.source, "ocr_conf": p.conf, "words": p.words},
        )
        written += 1
    return written


def _upsert_sql(content_id, pages: Sequence[PageWrite], now: datetime) -> int:
    placeholders = "(%s, %s, %s, %s, %s, %s::jsonb, 1, 'en', %s, %s)"
    params: list = []
    for p in pages:
        params += [
            str(content_id),
            p.page,
            p.text.replace("\x00", ""),
            p.source,
            p.conf,
            json.dumps(p.words) if p.words is not None else None,
            now,
            now,
        ]
    with connection.cursor() as cursor:
        cursor.execute(_UPSERT.format(values=", ".join([placeholders] * len(pages))), params)
        return cursor.rowcount


def record_text_progress(content_id, pages_done: int) -> None:
    """`text_pages_done` only ever grows, even when two chunk jobs finish out of order."""
    FileContent.objects.filter(pk=content_id).update(
        text_pages_done=Greatest(F("text_pages_done"), Value(pages_done)), updated_at=timezone.now()
    )
