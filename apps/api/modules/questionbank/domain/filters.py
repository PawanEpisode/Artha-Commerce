"""
QuestionFilter v1 schema and parsing (F-06 ERD 3.2).
Used by selectors, search, saved filters, share links, and practice pickers.
"""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Literal, TypedDict


class QuestionFilter(TypedDict, total=False):
    scope: Literal["public", "mine", "collection"]
    course: str
    level: str
    subject_key: str
    chapter_ids: list[uuid.UUID]
    topic_id: uuid.UUID
    include_secondary: bool
    scheme: Literal["current", "any"]
    kinds: list[str]
    source_kinds: list[str]
    ownership: list[str]
    year_from: int
    year_to: int
    term_codes: list[str]
    marks_min: Decimal
    marks_max: Decimal
    difficulty: list[int]
    bloom: list[str]
    nature: list[str]
    tags: list[str]
    reference_keys: list[str]
    q: str
    collection_id: uuid.UUID
    verified_only: bool
    exclude_ids: list[uuid.UUID]
    personal: Literal["unattempted", "attempted", "wrong_last", "never_correct", "bookmarked", "doubt", "due"]


def parse_filter_params(params: dict[str, Any]) -> QuestionFilter:
    """Parse query parameters or JSON dictionary into a typed QuestionFilter."""
    flt: QuestionFilter = {}

    if "scope" in params and params["scope"] in ("public", "mine", "collection"):
        flt["scope"] = params["scope"]
    else:
        flt["scope"] = "public"

    if "course" in params and params["course"]:
        flt["course"] = str(params["course"]).strip()
    if "level" in params and params["level"]:
        flt["level"] = str(params["level"]).strip()
    if "subject_key" in params and params["subject_key"]:
        flt["subject_key"] = str(params["subject_key"]).strip()

    if "chapter_ids" in params and params["chapter_ids"]:
        raw_ids = params["chapter_ids"]
        if isinstance(raw_ids, str):
            raw_ids = [s.strip() for s in raw_ids.split(",") if s.strip()]
        flt["chapter_ids"] = [uuid.UUID(str(ch)) for ch in raw_ids]

    if "topic_id" in params and params["topic_id"]:
        flt["topic_id"] = uuid.UUID(str(params["topic_id"]))

    if "include_secondary" in params:
        val = params["include_secondary"]
        flt["include_secondary"] = val is True or str(val).lower() in ("true", "1")

    if "scheme" in params and params["scheme"] in ("current", "any"):
        flt["scheme"] = params["scheme"]
    else:
        flt["scheme"] = "current"

    def _parse_str_list(key: str) -> list[str] | None:
        if key in params and params[key]:
            val = params[key]
            if isinstance(val, str):
                return [s.strip() for s in val.split(",") if s.strip()]
            if isinstance(val, (list, tuple)):
                return [str(s).strip() for s in val if str(s).strip()]
        return None

    for list_key in ("kinds", "source_kinds", "ownership", "term_codes", "bloom", "nature", "tags", "reference_keys"):
        parsed = _parse_str_list(list_key)
        if parsed:
            flt[list_key] = parsed  # type: ignore[literal-required]

    if "year_from" in params and params["year_from"] is not None:
        try:
            flt["year_from"] = int(params["year_from"])
        except (ValueError, TypeError):
            pass

    if "year_to" in params and params["year_to"] is not None:
        try:
            flt["year_to"] = int(params["year_to"])
        except (ValueError, TypeError):
            pass

    if "marks_min" in params and params["marks_min"] is not None:
        try:
            flt["marks_min"] = Decimal(str(params["marks_min"]))
        except InvalidOperation:
            pass

    if "marks_max" in params and params["marks_max"] is not None:
        try:
            flt["marks_max"] = Decimal(str(params["marks_max"]))
        except InvalidOperation:
            pass

    if "difficulty" in params and params["difficulty"]:
        raw_diff = params["difficulty"]
        if isinstance(raw_diff, (int, str)):
            raw_diff = [raw_diff]
        diffs = []
        for d in raw_diff:
            try:
                diffs.append(int(d))
            except (ValueError, TypeError):
                pass
        if diffs:
            flt["difficulty"] = diffs

    if "q" in params and params["q"]:
        flt["q"] = str(params["q"]).strip()

    if "collection_id" in params and params["collection_id"]:
        flt["collection_id"] = uuid.UUID(str(params["collection_id"]))

    if "verified_only" in params:
        val = params["verified_only"]
        flt["verified_only"] = val is True or str(val).lower() in ("true", "1")

    if "exclude_ids" in params and params["exclude_ids"]:
        raw_ex = params["exclude_ids"]
        if isinstance(raw_ex, str):
            raw_ex = [s.strip() for s in raw_ex.split(",") if s.strip()]
        flt["exclude_ids"] = [uuid.UUID(str(e)) for e in raw_ex]

    if "personal" in params and params["personal"] in (
        "unattempted",
        "attempted",
        "wrong_last",
        "never_correct",
        "bookmarked",
        "doubt",
        "due",
    ):
        flt["personal"] = params["personal"]

    return flt
