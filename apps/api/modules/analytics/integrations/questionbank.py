"""
Adapter for Question Bank (F-06 questionbank module).
"""

from __future__ import annotations

import uuid
from typing import Any

from modules.questionbank.models import Question, QuestionVersion


def get_labels_of_versions(version_ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    """
    Returns labels (difficulty, source_kind, suggested_seconds, primary_topic_id,
    subject_key, chapter_key) keyed by QuestionVersion id.
    """
    if not version_ids:
        return {}

    versions = (
        QuestionVersion.objects.filter(id__in=version_ids)
        .select_related("question")
        .values(
            "id",
            "suggested_seconds",
            "question__id",
            "question__difficulty",
            "question__source_kind",
            "question__primary_topic_id",
            "question__primary_chapter_id",
            "question__subject_key",
            "question__chapter_key",
        )
    )

    result: dict[uuid.UUID, dict[str, Any]] = {}
    for v in versions:
        result[v["id"]] = {
            "question_id": v["question__id"],
            "difficulty": v["question__difficulty"] or 0,
            "source_kind": v["question__source_kind"] or "platform",
            "suggested_seconds": v["suggested_seconds"],
            "primary_topic_id": v["question__primary_topic_id"],
            "primary_chapter_id": v["question__primary_chapter_id"],
            "subject_key": v["question__subject_key"] or "",
            "chapter_key": v["question__chapter_key"] or "",
        }

    return result


def find_fix_candidates(
    *,
    chapter_id: uuid.UUID | None = None,
    topic_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[uuid.UUID]:
    """
    Finds playable candidate question IDs for a weak chapter or topic.
    """
    qs = Question.objects.filter(deleted_at__isnull=True, current_version__state="live")
    if topic_id:
        qs = qs.filter(primary_topic_id=topic_id)
    elif chapter_id:
        qs = qs.filter(primary_chapter_id=chapter_id)

    return list(qs.order_by("?")[:limit].values_list("id", flat=True))
