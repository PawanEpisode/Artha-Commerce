"""
Adapter for Syllabus Module (F-02 syllabus module).
"""

from __future__ import annotations

import uuid
from typing import Any

from modules.syllabus.models import Chapter, Subject, Topic


def get_subject_by_key_or_id(subject_id_or_key: str | uuid.UUID) -> dict[str, Any] | None:
    """Returns subject info by id or key."""
    qs = Subject.objects.select_related("scheme__level__course")
    try:
        if isinstance(subject_id_or_key, uuid.UUID):
            subj = qs.get(id=subject_id_or_key)
        else:
            subj = qs.filter(key=str(subject_id_or_key)).first()
    except Subject.DoesNotExist:
        return None

    if not subj:
        return None

    return {
        "id": subj.id,
        "key": subj.key,
        "name": subj.name,
        "course_id": subj.scheme.level.course_id,
        "level_id": subj.scheme.level_id,
        "total_marks": subj.total_marks or 100,
    }


def list_chapters_for_subject(subject_id: uuid.UUID) -> list[dict[str, Any]]:
    """Returns list of active chapters for a subject with their estimated marks/weights."""
    chapters = Chapter.objects.filter(subject_id=subject_id, is_active=True).order_by("sort_order")
    res: list[dict[str, Any]] = []
    for c in chapters:
        weight = float(c.marks_max or c.marks_min or 5.0)
        res.append({
            "id": c.id,
            "key": c.key,
            "name": c.name,
            "weight": weight,
        })
    return res


def get_chapter_by_id(chapter_id: uuid.UUID) -> dict[str, Any] | None:
    """Returns chapter info by id."""
    ch = Chapter.objects.filter(id=chapter_id).first()
    if not ch:
        return None
    return {
        "id": ch.id,
        "key": ch.key,
        "name": ch.name,
        "weight": float(ch.marks_max or ch.marks_min or 5.0),
        "subject_id": ch.subject_id,
    }


def get_topic_name(topic_id: uuid.UUID) -> str:
    """Returns topic name by id."""
    t = Topic.objects.filter(id=topic_id).first()
    return t.name if t else "Topic"
