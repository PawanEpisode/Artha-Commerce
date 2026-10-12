"""One versioned, withdrawable consent per student before her text goes to Google (stored on `recall_settings`)."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ..domain import ai_consent as text
from ..errors import AiNotConsented, AiUnavailable, ConsentVersionMismatch
from ..models import RecallAuditLog, RecallSettings
from . import ai_gate


def _row(user_id, *, lock: bool = False) -> RecallSettings:
    RecallSettings.objects.bulk_create([RecallSettings(user_id=user_id)], ignore_conflicts=True)
    qs = RecallSettings.objects.select_for_update() if lock else RecallSettings.objects
    return qs.get(pk=user_id)


def is_valid(row: RecallSettings | None) -> bool:
    """Agreed to THIS version and not withdrawn since."""
    if row is None or row.ai_consent_version != text.VERSION or row.ai_consent_at is None:
        return False
    return row.ai_consent_withdrawn_at is None or row.ai_consent_withdrawn_at < row.ai_consent_at


def has_consent(user_id) -> bool:
    return is_valid(RecallSettings.objects.filter(pk=user_id).first())


def require(user_id) -> None:
    if not has_consent(user_id):
        raise AiNotConsented(extra={"version": text.VERSION})


@transaction.atomic
def grant(user_id, version: str) -> RecallSettings:
    """A stale version is 409; AI not set up is 503 (nothing recorded)."""
    if not ai_gate.available():
        raise AiUnavailable
    if version != text.VERSION:
        raise ConsentVersionMismatch
    row = _row(user_id, lock=True)
    row.ai_consent_version, row.ai_consent_at, row.ai_consent_withdrawn_at = text.VERSION, timezone.now(), None
    row.save(update_fields=["ai_consent_version", "ai_consent_at", "ai_consent_withdrawn_at", "updated_at"])
    RecallAuditLog.objects.create(
        actor_id=user_id,
        action="ai_consent",
        target_kind="settings",
        target_id=str(user_id),
        detail={"v": 1, "given": True},
    )
    return row


def withdraw(user_id) -> dict:
    """Never gated by the flag or by availability: she can always take it back. Waiting drafts and queued batches are removed."""
    from . import suggestions

    with transaction.atomic():
        row = _row(user_id, lock=True)
        row.ai_consent_withdrawn_at = timezone.now()
        row.save(update_fields=["ai_consent_withdrawn_at", "updated_at"])
        RecallAuditLog.objects.create(
            actor_id=user_id,
            action="ai_consent",
            target_kind="settings",
            target_id=str(user_id),
            detail={"v": 1, "given": False},
        )
    return suggestions.discard_waiting(user_id)
