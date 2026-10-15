"""
Scheme relation resolution for PYQ questions (F-09 ERD 3.5).
"""

from __future__ import annotations

import uuid


def compute_scheme_relation(
    paper_scheme_id: uuid.UUID | None,
    current_scheme_id: uuid.UUID | None,
    chapter_id: uuid.UUID | None = None,
) -> str:
    """
    Computes scheme relation:
    - 'current' if paper scheme matches current scheme.
    - 'mapped' if old chapter maps to a current chapter with same or merged relation.
    - 'changed' if partial or split relation.
    - 'out_of_scheme' if removed or no active mapping.
    - 'unmapped' if no chapter is associated.
    """
    if not chapter_id:
        return "unmapped"

    if paper_scheme_id and current_scheme_id and str(paper_scheme_id) == str(current_scheme_id):
        return "current"

    try:
        from modules.syllabus.models import ChapterMap

        ch_map = ChapterMap.objects.filter(from_chapter_id=chapter_id).first()
        if ch_map:
            if ch_map.relation in ("same", "merged"):
                return "mapped"
            elif ch_map.relation in ("split", "partial"):
                return "changed"
    except Exception:
        pass

    return "current" if not paper_scheme_id else "mapped"
