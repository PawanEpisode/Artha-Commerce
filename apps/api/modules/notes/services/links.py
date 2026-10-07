"""
Taxonomy links (ERD section 2 header): `link_columns(chapter_id, topic_id)` is the one place that writes the foreign keys and
their stable key copies together, so a row can never hold a chapter without its keys. Resolution goes through
`syllabus.selectors` only.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.syllabus import selectors as syllabus

from ..errors import UnknownChapter

UNLINKED: dict[str, Any] = {
    "level_id": None,
    "subject_id": None,
    "chapter_id": None,
    "topic_id": None,
    "subject_key": None,
    "chapter_key": None,
    "topic_key": None,
}


def link_columns(chapter_id: UUID | None, topic_id: UUID | None = None) -> dict[str, Any]:
    """Model field values for a chapter (and optional topic) of the syllabus; both None means Unfiled."""
    if chapter_id is None and topic_id is None:
        return dict(UNLINKED)
    topic = None
    if topic_id is not None:
        topic = syllabus.topic_refs([topic_id]).get(topic_id)
        if topic is None or (chapter_id is not None and topic.chapter_id != chapter_id):
            raise UnknownChapter("That topic does not belong to the chapter.")
        chapter_id = topic.chapter_id
    chapter = syllabus.chapter_refs([chapter_id]).get(chapter_id)
    if chapter is None:
        raise UnknownChapter
    return {
        "level_id": chapter.level_id,
        "subject_id": chapter.subject_id,
        "chapter_id": chapter.id,
        "topic_id": topic.id if topic else None,
        "subject_key": chapter.subject_key,
        "chapter_key": chapter.key,
        "topic_key": topic.key if topic else None,
    }


def columns_key(columns: dict[str, Any]) -> tuple | None:
    """`link_key` of a dict of link columns (what `link_columns` returns)."""
    if columns.get("chapter_id") is None:
        return None
    return (columns["level_id"], columns["subject_key"], columns["chapter_key"], columns["chapter_id"])


def link_key(row) -> tuple | None:
    """`(level_id, subject_key, chapter_key, chapter_id)` of any row with link columns, or None when Unfiled (what counts group by)."""
    if row.chapter_id is None:
        return None
    return (row.level_id, row.subject_key, row.chapter_key, row.chapter_id)
