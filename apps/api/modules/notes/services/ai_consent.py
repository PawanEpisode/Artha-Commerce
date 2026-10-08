"""One versioned, withdrawable AI consent per student (FR-F03-57), stored on `notes_settings`."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ..domain import ai_consent as text
from ..errors_ai import AiNotConsented, AiUnavailable, ConsentVersionMismatch
from ..models import Settings
from . import ai_gate, ai_jobs
from . import settings as settings_service


def is_valid(row: Settings) -> bool:
    """Agreed to THIS version and not withdrawn since."""
    if row.ai_consent_version != text.VERSION or row.ai_consent_at is None:
        return False
    return row.ai_consent_withdrawn_at is None or row.ai_consent_withdrawn_at < row.ai_consent_at


def has_consent(user_id) -> bool:
    row = Settings.objects.filter(pk=user_id).first()
    return row is not None and is_valid(row)


def require(user_id) -> None:
    if not has_consent(user_id):
        raise AiNotConsented(extra={"version": text.VERSION})


def status(user_id) -> dict:
    row = settings_service.get_or_create_settings(user_id)
    return {
        "text": text.text(),
        "consented": is_valid(row),
        "version": row.ai_consent_version,
        "consented_at": row.ai_consent_at,
        "withdrawn_at": row.ai_consent_withdrawn_at,
        "available": ai_gate.available("summary") or ai_gate.available("ocr"),
    }


@transaction.atomic
def grant(user_id, version: str) -> Settings:
    """Records agreement to the version the student saw. A stale version is 409; AI not set up is 503 (nothing recorded)."""
    if not (ai_gate.available("summary") or ai_gate.available("ocr")):
        raise AiUnavailable
    if version != text.VERSION:
        raise ConsentVersionMismatch
    settings_service.get_or_create_settings(user_id)
    row = Settings.objects.select_for_update().get(pk=user_id)
    row.ai_consent_version = text.VERSION
    row.ai_consent_at = timezone.now()
    row.ai_consent_withdrawn_at = None
    row.save()
    return row


def withdraw(user_id) -> dict:
    """Never gated by the flag or by availability: a student can always take consent back. Drafts are deleted."""
    with transaction.atomic():
        settings_service.get_or_create_settings(user_id)
        row = Settings.objects.select_for_update().get(pk=user_id)
        row.ai_consent_withdrawn_at = timezone.now()
        row.save()
    return ai_jobs.discard_all_for_user(user_id)
