"""
AI-suggested cards (FR-F15-18 to 20, R2-W5). The request path (gates, her material, cache, budget, the atomic quota charge, the
queue) runs in the API; `run_batch` runs in the worker and is the only place that calls the model, through `adapters/ai.py`.
A suggestion is a draft: nothing becomes a card without her Accept, and a draft is kept only when its quote is verbatim in the
material she supplied (`domain.suggestions`).

Order of the refusals in `request_batch`: replay by client id (no charge) -> flag (view) -> AI available (503) -> consent (403)
-> chapter (422) -> sources (422) -> enough material (422) -> cache (no charge) -> a batch already running for the chapter (no
charge) -> budget (503) -> quota (429, nothing written).
No text of hers is logged, put in a job payload, an event or the ledger. The only copy of pasted text is on the batch, emptied
the moment the job ends.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core import jobs as core_jobs
from core import suggestion_source_port as port

from ..adapters import ai as ai_adapter
from ..adapters import syllabus as syllabus_adapter
from ..domain import cards as card_domain
from ..domain import suggestions as sdomain
from ..errors import (
    NotEnoughMaterial,
    SourceUnavailable,
    SuggestionDecided,
    SuggestionNotReady,
)
from ..models import (
    RecallAiCall,
    RecallItem,
    RecallSuggestion,
    RecallSuggestionBatch,
    RecallSuggestionReject,
)
from . import ai_consent, ai_gate, ai_quota, cards

logger = logging.getLogger(__name__)

JOB_SUGGEST = "recall.suggest"
MAX_ATTEMPTS = 2  # a model call costs money: one retry for a network failure, not five
PIECES_PER_SOURCE = 40
Batch = RecallSuggestionBatch


@dataclass(frozen=True)
class BatchRequest:
    batch: Batch
    created: bool  # a new batch was queued (and charged)
    reused: (
        str | None
    )  # "cache" or "active" when an earlier batch was returned instead (nothing charged, nothing queued)
    estimate_seconds: int


# ------------------------------------------------------------------------------------------------ gathering material


def gather(user_id, chapter_id: UUID, sources: list[str], pasted_text: str) -> list[sdomain.SourceText]:
    """Her own material of the chapter from each chosen source, cleaned and cut to the size limit."""
    pieces: list[sdomain.SourceText] = []
    for name in sources:
        if name == "pasted":
            pieces.append(sdomain.SourceText("pasted", "Pasted text", pasted_text[: sdomain.MAX_PASTED_CHARS]))
            continue
        provider = port.get_suggestion_source(name)
        if provider is None:
            raise SourceUnavailable(extra={"sources": [name]})
        for p in provider.texts_for(user_id, chapter_id, limit=PIECES_PER_SOURCE):
            pieces.append(sdomain.SourceText(p.ref, p.label, p.text))
    return sdomain.pack_sources(pieces)


def _clean_request(sources: list[str], kinds: list[str], count: int) -> tuple[list[str], list[str]]:
    wanted = [s for s in sdomain.SOURCE_KINDS if s in sources]
    missing = [s for s in wanted if s != "pasted" and port.get_suggestion_source(s) is None]
    if missing:
        raise SourceUnavailable(extra={"sources": missing})
    chosen = [k for k in card_domain.KINDS if k in kinds] or list(card_domain.KINDS)
    return wanted, chosen


# ---------------------------------------------------------------------------------------------------- the request


def request_batch(
    user_id,
    *,
    chapter_id: UUID,
    sources: list[str],
    pasted_text: str = "",
    count: int = sdomain.DEFAULT_COUNT,
    kinds: list[str] | None = None,
    client_id: UUID | None = None,
) -> BatchRequest:
    if client_id is not None:
        replay = Batch.objects.filter(user_id=user_id, client_id=client_id).first()
        if replay is not None:
            return BatchRequest(replay, False, "replay", 0)
    ai_gate.require()
    ai_consent.require(user_id)
    syllabus_adapter.link_columns(chapter_id)  # 422 unknown_chapter
    wanted, chosen = _clean_request(sources, kinds or [], count)
    pasted = pasted_text.strip() if "pasted" in wanted else ""
    if "pasted" in wanted and not pasted:
        wanted.remove("pasted")
    if not wanted:
        raise NotEnoughMaterial
    packed = gather(user_id, chapter_id, wanted, pasted)
    chars = sdomain.total_chars(packed)
    if chars < sdomain.MIN_SOURCE_CHARS:
        raise NotEnoughMaterial
    digest = sdomain.source_hash(packed, chosen, count)
    now = timezone.now()
    cached = (
        Batch.objects.filter(
            user_id=user_id,
            source_hash=digest,
            prompt_version=sdomain.PROMPT_VERSION,
            status="ready",
            created_at__gte=now - timedelta(days=sdomain.CACHE_DAYS),
            suggestions__status="draft",
        )
        .order_by("-created_at")
        .distinct()
        .first()
    )
    if cached is not None:
        return BatchRequest(cached, False, "cache", 0)
    running = Batch.objects.filter(user_id=user_id, chapter_id=chapter_id, status__in=Batch.ACTIVE).first()
    if running is not None:
        return BatchRequest(running, False, "active", sdomain.estimate_seconds(running.source_chars))
    ai_gate.check_budget(now)
    day = ai_quota.today(now)
    try:
        with transaction.atomic():  # a failure below undoes the quota charge with it
            ai_quota.charge(user_id, day, count)
            batch = Batch.objects.create(
                user_id=user_id,
                client_id=client_id,
                chapter_id=chapter_id,
                sources=wanted,
                kinds=chosen,
                requested_count=count,
                source_hash=digest,
                source_chars=chars,
                pasted_text=pasted,
                prompt_id=sdomain.PROMPT_ID,
                prompt_version=sdomain.PROMPT_VERSION,
                charged_suggestions=count,
                usage_day=day,
            )
            core_jobs.enqueue(
                JOB_SUGGEST,
                {"batch_id": str(batch.id)},
                dedupe_key=f"{JOB_SUGGEST}:{batch.id}",
                max_attempts=MAX_ATTEMPTS,
            )
    except IntegrityError:  # the same client id raced us; the charge rolled back with the transaction
        replay = Batch.objects.filter(user_id=user_id, client_id=client_id).first() if client_id else None
        if replay is None:
            raise
        return BatchRequest(replay, False, "replay", 0)
    return BatchRequest(batch, True, None, sdomain.estimate_seconds(chars))


# ------------------------------------------------------------------------------------------------------ the worker


class _Known:
    """Fingerprints that must not be suggested: a card she has now, or a draft she rejected in the last 90 days."""

    def __init__(self, user_id):
        self.user_id = user_id
        self.cutoff = timezone.now() - timedelta(days=sdomain.REJECT_MEMORY_DAYS)

    def __contains__(self, fp: object) -> bool:
        if not isinstance(fp, str):
            return False
        if RecallSuggestionReject.objects.filter(
            user_id=self.user_id, fingerprint=fp, created_at__gte=self.cutoff
        ).exists():
            return True
        return RecallItem.objects.filter(
            owner_user_id=self.user_id, ownership="user", fingerprint=fp, status__in=["active", "archived"]
        ).exists()


def _last_attempt() -> bool:
    job = core_jobs.current_job()
    return job is not None and job.attempts >= job.max_attempts


def _close(batch: Batch, status: str, *, error: str = "", refund_all: bool = False) -> None:
    """Ends a batch that produced nothing: the pasted text is emptied and the whole charge (batch included) is given back."""
    batch.status, batch.error_code, batch.finished_at, batch.pasted_text = status, error, timezone.now(), ""
    if refund_all and not batch.refunded:
        ai_quota.refund(batch.user_id, batch.usage_day, suggestions=batch.charged_suggestions, batch=True)
        batch.refunded = True
    batch.save(update_fields=["status", "error_code", "finished_at", "pasted_text", "refunded", "updated_at"])
    if status == "failed":
        _notify_suggestions_failed(batch)


def _notify_suggestions_ready(batch: Batch) -> None:
    user_id = batch.user_id
    batch_id = str(batch.id)

    def _send():
        try:
            from modules.notifications.services.notify import notify

            notify(
                user_id,
                "recall_suggestions_ready",
                context={"batch_id": batch_id, "failed": False},
                dedupe_ref={"batch_id": batch_id},
            )
        except Exception:
            logger.exception("Failed to send recall_suggestions_ready notification")

    transaction.on_commit(_send)


def _notify_suggestions_failed(batch: Batch) -> None:
    user_id = batch.user_id
    batch_id = str(batch.id)

    def _send():
        try:
            from modules.notifications.services.notify import notify

            notify(
                user_id,
                "recall_suggestions_ready",
                context={"batch_id": batch_id, "failed": True},
                dedupe_ref={"batch_id": batch_id},
            )
        except Exception:
            logger.exception("Failed to send recall_suggestions_ready failure notification")

    transaction.on_commit(_send)


def _ledger(batch: Batch, status: str, *, result=None, latency_ms: int = 0, error: str = "") -> int:
    cost = 0
    if result is not None:
        cost = sdomain.cost_paise(
            result.input_tokens,
            result.output_tokens,
            settings.GEMINI_PRICE_IN_PAISE_PER_M,
            settings.GEMINI_PRICE_OUT_PAISE_PER_M,
        )
    RecallAiCall.objects.create(
        user_id=batch.user_id,
        batch_id=batch.id,
        prompt_id=batch.prompt_id,
        prompt_version=batch.prompt_version,
        model=getattr(result, "model", "") or "",
        tokens_in=getattr(result, "input_tokens", 0),
        tokens_out=getattr(result, "output_tokens", 0),
        cost_paise=cost,
        latency_ms=latency_ms,
        status=status,
        error_code=error,
    )
    return cost


def run_batch(payload: dict) -> dict:
    """
    Worker handler for `recall.suggest`. Re-checks what can change between the request and now (AI available, consent still
    given, material still there), calls the model once, keeps only drafts whose evidence is verbatim, stores them. A network
    error is retried by the queue once; on the last attempt the batch is closed and its whole charge refunded.
    """
    import time

    batch_id = payload["batch_id"]
    with transaction.atomic():
        batch = Batch.objects.select_for_update().filter(pk=batch_id).first()
        if batch is None or batch.status not in Batch.ACTIVE:
            return {"skipped": True}
        if ai_gate.unavailable_reason() is not None:
            _close(batch, "cancelled", error="unavailable", refund_all=True)
            return {"status": "cancelled", "reason": "unavailable"}
        if not ai_consent.has_consent(batch.user_id):
            _close(batch, "cancelled", error="consent_withdrawn", refund_all=True)
            return {"status": "cancelled", "reason": "consent_withdrawn"}
        try:
            material = gather(batch.user_id, batch.chapter_id, list(batch.sources), batch.pasted_text)
        except SourceUnavailable:
            _close(batch, "failed", error="source_unavailable", refund_all=True)
            return {"status": "failed", "reason": "source_unavailable"}
        if sdomain.total_chars(material) < sdomain.MIN_SOURCE_CHARS:
            _close(batch, "failed", error="too_little", refund_all=True)
            return {"status": "failed", "reason": "too_little"}
        if batch.status == "queued":
            batch.status = "running"
            batch.save(update_fields=["status", "updated_at"])
    started = time.monotonic()
    try:
        result = ai_adapter.generate(material, list(batch.kinds), batch.requested_count)
        core_jobs.heartbeat()
    except ai_adapter.GeminiBlocked:
        return _fail(batch_id, "blocked", ledger="blocked", started=started)
    except (ai_adapter.GeminiError, ai_adapter.GeminiNotConfigured):
        if _last_attempt():
            return _fail(batch_id, "model_error", ledger="failed", started=started)
        raise
    return _store(batch_id, result, material, int((time.monotonic() - started) * 1000))


def _fail(batch_id, code: str, *, ledger: str, started: float) -> dict:
    import time

    with transaction.atomic():
        batch = Batch.objects.select_for_update().get(pk=batch_id)
        if batch.status in Batch.ACTIVE:
            _ledger(batch, ledger, latency_ms=int((time.monotonic() - started) * 1000), error=code)
            _close(batch, "failed", error=code, refund_all=True)
    return {"status": "failed", "reason": code}


def _store(batch_id, result, material: list[sdomain.SourceText], latency_ms: int) -> dict:
    now = timezone.now()
    with transaction.atomic():
        batch = Batch.objects.select_for_update().get(pk=batch_id)
        if batch.status not in Batch.ACTIVE:
            return {"status": batch.status}
        cost = _ledger(batch, "ok", result=result, latency_ms=latency_ms)
        if not ai_consent.has_consent(batch.user_id):  # withdrawn while the model was thinking: keep nothing
            _close(batch, "cancelled", error="consent_withdrawn", refund_all=True)
            return {"status": "cancelled", "reason": "consent_withdrawn"}
        parsed = sdomain.parse_answer(
            result.text, material, list(batch.kinds), batch.requested_count, known=_Known(batch.user_id)
        )
        rows = [
            RecallSuggestion(
                batch=batch,
                user_id=batch.user_id,
                position=i,
                kind=d.kind,
                fields=d.fields,
                evidence_quote=d.evidence_quote,
                evidence_source=d.evidence_source,
                fingerprint=card_domain.fingerprint(d.kind, d.fields),
            )
            for i, d in enumerate(parsed.drafts)
        ]
        RecallSuggestion.objects.bulk_create(rows)
        batch.produced, batch.dropped = len(rows), parsed.dropped
        if not rows:  # the model was paid for but nothing survived: the student is not charged for an empty batch
            _close(batch, "failed", error="nothing_usable", refund_all=True)
            return {"status": "failed", "reason": "nothing_usable", "dropped": parsed.dropped, "cost_paise": cost}
        ai_quota.refund(batch.user_id, batch.usage_day, suggestions=batch.charged_suggestions - len(rows), batch=False)
        batch.status, batch.finished_at, batch.pasted_text = "ready", now, ""
        batch.expires_at = now + timedelta(days=sdomain.DRAFT_DAYS)
        batch.save()
        _notify_suggestions_ready(batch)
    return {"status": "ready", "produced": len(rows), "dropped": parsed.dropped, "cost_paise": cost}


def give_up(payload: dict) -> None:
    """The queue closed the job because workers kept going silent: close the batch and refund."""
    with transaction.atomic():
        batch = Batch.objects.select_for_update().filter(pk=payload.get("batch_id")).first()
        if batch is not None and batch.status in Batch.ACTIVE:
            _close(batch, "failed", error="model_error", refund_all=True)


# ------------------------------------------------------------------------------------------------ decide on a draft


@dataclass(frozen=True)
class Decision:
    suggestion: RecallSuggestion
    created: cards.CreatedCards | None


def _locked(user_id, suggestion_id) -> RecallSuggestion:
    from rest_framework.exceptions import NotFound

    row = (
        RecallSuggestion.objects.select_for_update()
        .select_related("batch")
        .filter(pk=suggestion_id, user_id=user_id)
        .first()
    )
    if row is None:
        raise NotFound("Suggestion not found.")
    return row


def accept(user_id, suggestion_id, *, fields: dict | None = None, force: bool = False) -> Decision:
    """
    Makes the card (kind, evidence-backed fields, or her edited fields). Idempotent: the suggestion id is the card's client id, so
    a second tap or another device gets the same card. A repeat of the decision is fine; the opposite decision is 409.
    `origin` is `ai_suggestion` and the card is private (`shareable = false`): the words are the model's, not hers.
    """
    with transaction.atomic():
        row = _locked(user_id, suggestion_id)
        if row.status == "rejected" or row.status == "expired":
            raise SuggestionDecided
        if row.batch.status != "ready" and row.status == "draft":
            raise SuggestionNotReady
        final = {**row.fields, **(fields or {})}
        edited = final != row.fields
        created = cards.create_card(
            user_id,
            kind=row.kind,
            fields=final,
            chapter_id=row.batch.chapter_id,
            importance="bullet",
            client_id=row.id,
            force=force,
            origin="ai_suggestion",
            origin_kind="ai_suggestion",
            origin_locator={"batch_id": str(row.batch_id)},
            shareable=False,
        )
        if row.status == "draft":
            row.status = "edited_accepted" if edited else "accepted"
            row.item_id, row.decided_at = created.item_id, timezone.now()
            row.save(update_fields=["status", "item_id", "decided_at", "updated_at"])
        return Decision(row, created)


def reject(user_id, suggestion_id) -> Decision:
    """Forgets the draft and remembers its fingerprint for 90 days so the same text is not suggested again."""
    with transaction.atomic():
        row = _locked(user_id, suggestion_id)
        if row.status in ("accepted", "edited_accepted"):
            raise SuggestionDecided
        if row.status == "draft":
            row.status, row.decided_at = "rejected", timezone.now()
            row.save(update_fields=["status", "decided_at", "updated_at"])
            RecallSuggestionReject.objects.get_or_create(user_id=user_id, fingerprint=row.fingerprint)
        return Decision(row, None)


# ------------------------------------------------------------------------------------------------ cleanup and rights


def discard_waiting(user_id) -> dict:
    """Consent withdrawn: waiting drafts are deleted and a queued or running batch is cancelled and refunded."""
    cancelled = deleted = 0
    with transaction.atomic():
        for batch in Batch.objects.select_for_update().filter(user_id=user_id, status__in=Batch.ACTIVE):
            _close(batch, "cancelled", error="consent_withdrawn", refund_all=True)
            cancelled += 1
        deleted = RecallSuggestion.objects.filter(user_id=user_id, status="draft").delete()[0]
        Batch.objects.filter(user_id=user_id, status="ready").update(status="expired")
    return {"cancelled": cancelled, "drafts_deleted": deleted}


def expire_drafts(*, now=None, limit: int = 500) -> dict:
    """Daily: drafts past their 30 days are deleted, batches older than 60 days go, reject memory past 90 days goes."""
    now = now or timezone.now()
    ids = list(Batch.objects.filter(status="ready", expires_at__lt=now).values_list("id", flat=True)[:limit])
    drafts = RecallSuggestion.objects.filter(batch_id__in=ids, status="draft").delete()[0]
    Batch.objects.filter(id__in=ids).update(status="expired")
    old = Batch.objects.filter(created_at__lt=now - timedelta(days=60), status__in=["expired", "failed", "cancelled"])
    removed = old.filter(id__in=list(old.values_list("id", flat=True)[:limit])).delete()[0]
    forgotten = RecallSuggestionReject.objects.filter(
        created_at__lt=now - timedelta(days=sdomain.REJECT_MEMORY_DAYS)
    ).delete()[0]
    return {"expired": len(ids), "drafts": drafts, "removed": removed, "rejects": forgotten}


def run_expiry(payload: dict) -> dict:
    return expire_drafts()
