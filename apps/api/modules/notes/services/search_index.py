"""
The stored search vectors (ERD 2.3, 2.4, 2.6): of a note (title weight A, body weight B), of a PDF page and of a mark (quote A,
comment B), each in the configuration its language needs (`english` for Latin text, `simple` for Hindi and mixed, where
stemming would hurt). Written in one UPDATE that does not touch `updated_at`. PostgreSQL only: on SQLite (tests) the vector
columns stay null and search falls back to substring match.
"""

from __future__ import annotations

from collections.abc import Iterable

from django.contrib.postgres.search import SearchVector
from django.db import connection
from django.db.models import Value

from ..domain.search_query import config_for, config_for_text, detect_lang
from ..models import Annotation, FilePage, Note


def refresh(note: Note) -> None:
    if connection.vendor != "postgresql":
        return
    config = config_for(note.lang)
    vector = SearchVector(Value(note.title), weight="A", config=config) + SearchVector(
        Value(note.body_text), weight="B", config=config
    )
    Note.objects.filter(pk=note.pk).update(search_tsv=vector)


# --- R2: PDF pages and marks ----------------------------------------------------------------------------------------------
def refresh_pages(content_id, pages: Iterable[int] | None = None) -> int:
    """
    Sets `lang` and the stored vector of the given pages of a file (all pages when `pages` is None), one UPDATE per language:
    `english` for Latin text, `simple` when Devanagari exceeds 30% of the letters. The extract and OCR workers call it after
    each chunk. `lang` is kept on SQLite too; the vector is PostgreSQL only. Returns the number of pages updated.
    """
    rows = FilePage.objects.filter(content_id=content_id)
    if pages is not None:
        rows = rows.filter(page__in=list(pages))
    by_lang: dict[str, list[int]] = {}
    for page, text in rows.values_list("page", "text"):
        by_lang.setdefault(detect_lang(text), []).append(page)
    updated = 0
    for lang, numbers in by_lang.items():
        values: dict = {"lang": lang}
        if connection.vendor == "postgresql":
            values["tsv"] = SearchVector("text", config=config_for(lang))
        updated += FilePage.objects.filter(content_id=content_id, page__in=numbers).update(**values)
    return updated


def refresh_annotation(annotation: Annotation) -> None:
    """The mark's vector from its quote (weight A) and comment (weight B), in the configuration its own text needs."""
    if connection.vendor != "postgresql":
        return
    quote, comment = annotation.quote_exact or "", annotation.comment or ""
    config = config_for_text(f"{quote} {comment}")
    vector = SearchVector(Value(quote), weight="A", config=config) + SearchVector(
        Value(comment), weight="B", config=config
    )
    Annotation.objects.filter(pk=annotation.pk).update(search_tsv=vector)
