"""Reads of the AI suggestion feature: the overview (is it on for her, what is left today), one batch with its drafts, her recent batches."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from core import suggestion_source_port as port

from ..domain import ai_consent as consent_text
from ..domain import suggestions as sdomain
from ..models import RecallSettings, RecallSuggestion, RecallSuggestionBatch
from ..services import ai_consent, ai_gate, ai_quota, quota


@dataclass(frozen=True)
class BatchView:
    batch: RecallSuggestionBatch
    suggestions: list[RecallSuggestion]


def overview(user_id) -> dict:
    """What the screen needs before it offers "Suggest cards": availability, consent, what is left of today's quota, the sources."""
    now_day = ai_quota.today()
    batches_used, cards_used = ai_quota.used(user_id, now_day)
    limits = quota.limits_for(user_id)
    row = RecallSettings.objects.filter(pk=user_id).first()
    return {
        "available": ai_gate.available(),
        "consent": {
            "version": consent_text.VERSION,
            "given": ai_consent.is_valid(row),
            "given_at": row.ai_consent_at if row is not None and ai_consent.is_valid(row) else None,
        },
        "quota": {
            "batches_used": batches_used,
            "batches_limit": limits.ai_batches_per_day,
            "suggestions_used": cards_used,
            "suggestions_limit": limits.ai_suggestions_per_day,
            "resets_on": ai_quota.resets_on(now_day),
        },
        "sources": [*port.available_sources(), "pasted"],
        "limits": {
            "min_count": sdomain.MIN_COUNT,
            "max_count": sdomain.MAX_COUNT,
            "default_count": sdomain.DEFAULT_COUNT,
            "max_pasted_chars": sdomain.MAX_PASTED_CHARS,
            "min_source_chars": sdomain.MIN_SOURCE_CHARS,
        },
        "waiting_drafts": RecallSuggestion.objects.filter(
            user_id=user_id, status="draft", batch__status="ready"
        ).count(),
    }


def consent_state(user_id) -> dict:
    row = RecallSettings.objects.filter(pk=user_id).first()
    valid = ai_consent.is_valid(row)
    return {
        **consent_text.text(),
        "consented": valid,
        "consented_at": row.ai_consent_at if valid and row is not None else None,
        "available": ai_gate.available(),
    }


def get_batch(user_id, batch_id: UUID) -> BatchView | None:
    batch = RecallSuggestionBatch.objects.filter(pk=batch_id, user_id=user_id).first()
    if batch is None:
        return None
    rows = list(RecallSuggestion.objects.filter(batch=batch).order_by("position", "id"))
    return BatchView(batch, rows)


def list_batches(user_id, *, chapter_id: UUID | None = None, limit: int = 20) -> list[BatchView]:
    qs = RecallSuggestionBatch.objects.filter(user_id=user_id).exclude(status="expired").order_by("-created_at")
    if chapter_id is not None:
        qs = qs.filter(chapter_id=chapter_id)
    batches = list(qs[:limit])
    by_batch: dict = {}
    for s in RecallSuggestion.objects.filter(batch__in=batches).order_by("position", "id"):
        by_batch.setdefault(s.batch_id, []).append(s)
    return [BatchView(b, by_batch.get(b.id, [])) for b in batches]
