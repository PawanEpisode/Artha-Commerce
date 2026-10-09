"""The student's notes settings (ERD 2.11): created on first read, updated by partial PUT."""

from __future__ import annotations

from django.db import transaction

from ..domain.legend import cleaned_legend
from ..models import Settings
from . import ai_gate, resumable, unlock

WRITABLE = ("color_legend", "default_color", "page_tone", "finger_draws", "ocr_default", "ocr_lang")


def get_or_create_settings(user_id) -> Settings:
    settings, _ = Settings.objects.get_or_create(user_id=user_id)
    return settings


@transaction.atomic
def update_settings(user_id, changes: dict) -> Settings:
    """Only the writable keys present in `changes` are applied (validated by the serializer at the edge)."""
    Settings.objects.get_or_create(user_id=user_id)
    settings = Settings.objects.select_for_update().get(pk=user_id)
    for key in WRITABLE:
        if key in changes:
            setattr(settings, key, cleaned_legend(changes[key]) if key == "color_legend" else changes[key])
    settings.save()
    return settings


def capabilities(user_id=None) -> dict[str, bool]:
    """What this student can do, for the settings screen: recall needs a registered provider that is on for her (F-15 flag)."""
    from core.recall_port import get_recall_provider, recall_available

    return {
        "recall": recall_available(user_id) if user_id is not None else get_recall_provider() is not None,
        "ocr_hindi": True,
        "ai_ocr": ai_gate.available("ocr"),
        "ai_summary": ai_gate.available("summary"),
        "unlock": unlock.available(),
        "resumable_upload": resumable.available(),
    }
