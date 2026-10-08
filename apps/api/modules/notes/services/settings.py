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


def capabilities() -> dict[str, bool]:
    """What this deployment can do, for the settings screen: recall exists only once F-15 registers a provider."""
    from core.recall_port import get_recall_provider

    return {
        "recall": get_recall_provider() is not None,
        "ocr_hindi": True,
        "ai_ocr": ai_gate.available("ocr"),
        "ai_summary": ai_gate.available("summary"),
        "unlock": unlock.available(),
        "resumable_upload": resumable.available(),
    }
