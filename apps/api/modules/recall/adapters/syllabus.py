"""
Syllabus adapter: resolves a chapter (and topic) to the link columns of a recall item, together with the stable keys that keep
a row valid across a scheme switch. Goes through `modules.syllabus.selectors` only, like `modules/notes/services/links.py`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from uuid import UUID

from modules.syllabus import selectors as syllabus

from ..errors import UnknownChapter

ChapterRef = syllabus.ChapterRef

UNLINKED: dict[str, Any] = {
    "course_id": None,
    "level_id": None,
    "scheme_id": None,
    "subject_id": None,
    "chapter_id": None,
    "topic_id": None,
    "subject_key": None,
    "chapter_key": None,
}


def link_columns(chapter_id: UUID | None, topic_id: UUID | None = None) -> dict[str, Any]:
    """Item field values for a chapter (and optional topic); both None means Unsorted. 422 `unknown_chapter` otherwise."""
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
    full = syllabus.get_chapter(chapter.id)  # the course id is not on the reference
    course_id = full.subject.scheme.level.course_id if full is not None else None
    return {
        "course_id": course_id,
        "level_id": chapter.level_id,
        "scheme_id": chapter.scheme_id,
        "subject_id": chapter.subject_id,
        "chapter_id": chapter.id,
        "topic_id": topic.id if topic else None,
        "subject_key": chapter.subject_key,
        "chapter_key": chapter.key,
    }


def chapter_refs(chapter_ids: Iterable[UUID | None]) -> Mapping[UUID, ChapterRef]:
    """Display references for the visible chapters among the ids (one query); the rest are simply absent."""
    return syllabus.chapter_refs([c for c in set(chapter_ids) if c is not None])
