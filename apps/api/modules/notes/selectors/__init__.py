"""
Public read interface of notes (ERD 3.2). Other modules import from here, never from `models`.

    counts_for_chapters(user_id, chapter_ids) -> {chapter_id: ChapterCounts}   F-02 chapter page, Today, analytics
    search(user_id, q, scope=..., flt=..., limit=..., cursor=...)              X-02 context agent, web search
    recent(user_id, limit=10)                                                  hub, Today
    aggregate(user_id, NoteFilter, tab=..., cursor=..., limit=...)             "everything for Subject X"
    chapter_overview(user_id, level_id, subject_key, chapter_key)              chapter page slot
    usage(user_id)                                                             plan limits and what is used
"""

from ._common import LinkView, NoteCard, NoteFilter, Page
from ._common import cards as cards_of
from .aggregate import AggregateItem, aggregate
from .counts import (
    ChapterCountRow,
    ChapterCounts,
    ChapterOverview,
    SubjectCounts,
    chapter_counts,
    chapter_overview,
    counts_for_chapters,
    subject_counts,
    unfiled_count,
)
from .export import export_all
from .notes import changes, get_note, get_version, list_notes, list_trash, list_versions, recent
from .search import SearchHit, search
from .suggest import suggestions_for
from .tags import TagView, get_tag, list_tags
from .usage import UsageView, usage

__all__ = [
    "AggregateItem",
    "ChapterCountRow",
    "ChapterCounts",
    "ChapterOverview",
    "LinkView",
    "NoteCard",
    "NoteFilter",
    "Page",
    "SearchHit",
    "SubjectCounts",
    "TagView",
    "UsageView",
    "aggregate",
    "cards_of",
    "changes",
    "chapter_counts",
    "chapter_overview",
    "counts_for_chapters",
    "export_all",
    "get_note",
    "get_tag",
    "get_version",
    "list_notes",
    "list_tags",
    "list_trash",
    "list_versions",
    "recent",
    "search",
    "subject_counts",
    "suggestions_for",
    "unfiled_count",
    "usage",
]
