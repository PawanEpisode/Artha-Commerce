"""
The `notes` source of recall's AI card suggestions (F-15 FR-F15-18): the student's own live notes and text highlights of one
chapter, handed over through `core.suggestion_source_port`. Notes never imports recall; recall never imports notes. Only her own
rows, by stable chapter keys (a syllabus scheme switch is harmless), plain text only, and never the AI summaries (a summary is
a model's words, not her material).
"""

from __future__ import annotations

from uuid import UUID

from core.suggestion_source_port import SourcePiece

from ..models import Annotation, Note
from . import links

HIGHLIGHT_KINDS = ("highlight", "underline", "sticky", "textbox")
PIECE_CHARS = 1500


class NotesSuggestionSource:
    def texts_for(self, user_id, chapter_id: UUID, *, limit: int) -> list[SourcePiece]:
        link = links.link_columns(chapter_id)
        keys = {"level_id": link["level_id"], "subject_key": link["subject_key"], "chapter_key": link["chapter_key"]}
        if keys["chapter_key"] is None:
            return []
        out: list[SourcePiece] = []
        notes = (
            Note.objects.filter(user_id=user_id, deleted_at__isnull=True, kind=Note.Kind.NOTE, **keys)
            .exclude(origin=Note.Origin.AI_SUMMARY)
            .order_by("-updated_at", "id")[:limit]
        )
        for n in notes:
            text = (n.body_text or "").strip()
            if text:
                out.append(SourcePiece(f"note:{n.id}", "Note", text[:PIECE_CHARS]))
        marks = (
            Annotation.objects.filter(
                user_id=user_id,
                deleted_at__isnull=True,
                kind__in=HIGHLIGHT_KINDS,
                document__deleted_at__isnull=True,
                **keys,
            )
            .select_related("document")
            .order_by("document_id", "page", "id")[:limit]
        )
        for a in marks:
            quote, comment = (a.quote_exact or "").strip(), (a.comment or "").strip()
            text = f"{quote}\nMy comment: {comment}" if quote and comment else quote or comment
            if text:
                out.append(SourcePiece(f"mark:{a.id}", f"Highlight, page {a.page}", text[:PIECE_CHARS]))
        return out[:limit]
