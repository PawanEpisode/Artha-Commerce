"""
The stored search vector of a note (ERD 2.4): title weight A, body weight B, in the configuration the note's language
needs (`english` for Latin text, `simple` for Hindi and mixed, where stemming would hurt). Written in one UPDATE that does
not touch `updated_at`. PostgreSQL only: on SQLite (tests) the column stays null and search falls back to substring match.
"""

from __future__ import annotations

from django.contrib.postgres.search import SearchVector
from django.db import connection
from django.db.models import Value

from ..domain.search_query import config_for
from ..models import Note


def refresh(note: Note) -> None:
    if connection.vendor != "postgresql":
        return
    config = config_for(note.lang)
    vector = SearchVector(Value(note.title), weight="A", config=config) + SearchVector(
        Value(note.body_text), weight="B", config=config
    )
    Note.objects.filter(pk=note.pk).update(search_tsv=vector)
