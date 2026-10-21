"""
Event subscribers for MCQ Bank (F-05 ERD 3.2, 3.3).
Handles collection updates, question takedowns, and preset use counting.
"""

from __future__ import annotations

import logging
import uuid

from django.db import models
from django.utils import timezone

from core.events import subscribe
from modules.questionbank.models import CollectionItem

from .models import McqSet, TestPreset

logger = logging.getLogger(__name__)


def refresh_set_counts(payload: dict) -> None:
    """Updates question_count for hosted sets when their underlying collection changes."""
    collection_id = payload.get("collection_id")
    if not collection_id:
        return
    try:
        coll_uuid = uuid.UUID(str(collection_id))
    except (ValueError, TypeError):
        return

    count = CollectionItem.objects.filter(collection_id=coll_uuid).count()
    McqSet.objects.filter(collection_id=coll_uuid).update(question_count=count)


def on_takedown(payload: dict) -> None:
    """Handles question takedowns; shrinks or alerts on affected sets."""
    question_id = payload.get("question_id")
    if not question_id:
        return
    # Refresh counts of any sets containing this question
    collection_ids = list(
        CollectionItem.objects.filter(question_id=question_id).values_list("collection_id", flat=True)
    )
    for cid in collection_ids:
        cnt = CollectionItem.objects.filter(collection_id=cid).count()
        McqSet.objects.filter(collection_id=cid).update(question_count=cnt)


def on_session_completed(payload: dict | None = None, **kwargs: Any) -> None:
    """Increments use_count on preset when session was created from a preset."""
    data = payload or kwargs.get("payload") or kwargs
    origin_module = data.get("origin_module")
    if origin_module != "mcq_bank":
        return
    origin_ref = payload.get("origin_ref", "")
    if origin_ref and origin_ref.startswith("preset:"):
        preset_id = origin_ref.split("preset:", 1)[1]
        try:
            p_uuid = uuid.UUID(preset_id)
            TestPreset.objects.filter(id=p_uuid).update(
                use_count=models.F("use_count") + 1,
                last_used_at=timezone.now(),
            )
        except Exception as exc:
            logger.warning("Failed to increment preset use count: %s", exc)


def register_subscribers() -> None:
    """Registers event handlers on the core event bus."""
    subscribe("collection_updated", refresh_set_counts)
    subscribe("question_taken_down", on_takedown)
    subscribe("question_unpublished", on_takedown)
    subscribe("practice_session_completed", on_session_completed)
