"""
AI exam summary (F-03 R3, FR-F03-57 to 60). The request path (consent, gather, cache, budget, atomic quota charge, queue) runs in
the API; `run_summary` runs in the worker and is the only place that calls Gemini. Accept turns the draft into a note of kind
`exam_summary` (one current per chapter); discard and expiry delete it.

Order of the refusals in `request_summary`: replay (no charge) -> AI available (503) -> consent (403) -> chapter (422) -> enough
material (422) -> cache (no charge) -> one active job per chapter (no charge) -> budget (503) -> quota (429, nothing written).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import jobs as core_jobs
from integrations import gemini

from .. import events
from ..domain import ai_consent as consent_text
from ..domain import summary as sdomain
from ..domain.quota import resets_on
from ..errors import QuotaExceeded
from ..errors_ai import DraftNotReady, NotEnoughMaterial
from ..models import AiJob, Annotation, Note
from . import ai_consent, ai_gate, ai_jobs, links, quota
from . import notes as note_services

logger = logging.getLogger(__name__)

JOB_SUMMARIZE = "notes.summarize"
INCLUDE = ("notes", "highlights")
HIGHLIGHT_KINDS = ("highlight", "underline", "sticky", "textbox", "area")
CACHE_HOURS = 24
MAX_ATTEMPTS = 2  # a model call costs money: one retry for a network failure, not five


@dataclass(frozen=True)
class SummaryRequest:
    job: AiJob
    created: bool  # a new job was queued (and charged)
    cached: bool  # an earlier job with the same inputs was returned instead: nothing charged, nothing queued
    estimate_seconds: int


# --- Gathering the inputs ------------------------------------------------------------------------------------------------
def _highlight_text(a: Annotation) -> str:
    quote = (a.quote_exact or "").strip()
    comment = (a.comment or "").strip()
    return sdomain.clip(f"{quote}\nMy comment: {comment}" if quote and comment else quote or comment, 1500)


def _note_item(ref: int, n: Note) -> sdomain.SummaryItem | None:
    text = sdomain.clip(n.body_text or "")
    if not text:
        return None
    return sdomain.SummaryItem(ref, "note", str(n.id), text, None, n.title.strip() or "Untitled note")


def _highlight_item(ref: int, a: Annotation) -> sdomain.SummaryItem | None:
    text = _highlight_text(a)
    if not text:
        return None
    return sdomain.SummaryItem(
        ref, "highlight", str(a.id), text, a.page, f"{a.document.title}, page {a.page}", str(a.document_id)
    )


def gather(user_id, link: dict, include: Iterable[str]) -> list[sdomain.SummaryItem]:
    """The student's own live notes and text marks of one chapter (by stable keys, so a syllabus scheme switch is harmless)."""
    include = set(include)
    keys = {"level_id": link["level_id"], "subject_key": link["subject_key"], "chapter_key": link["chapter_key"]}
    items: list[sdomain.SummaryItem] = []
    if "notes" in include:
        notes = (
            Note.objects.filter(user_id=user_id, deleted_at__isnull=True, kind=Note.Kind.NOTE, **keys)
            .exclude(origin=Note.Origin.AI_SUMMARY)
            .order_by("-updated_at", "id")[: sdomain.MAX_ITEMS]
        )
        for n in notes:
            item = _note_item(len(items) + 1, n)
            if item:
                items.append(item)
    if "highlights" in include:
        marks = (
            Annotation.objects.filter(
                user_id=user_id,
                deleted_at__isnull=True,
                kind__in=HIGHLIGHT_KINDS,
                document__deleted_at__isnull=True,
                **keys,
            )
            .select_related("document")
            .order_by("document_id", "page", "id")[: sdomain.MAX_ITEMS]
        )
        for a in marks:
            item = _highlight_item(len(items) + 1, a)
            if item:
                items.append(item)
    return items


def gather_by_ids(user_id, refs: list[dict]) -> list[sdomain.SummaryItem]:
    """The same inputs the request chose, re-read now (an edit made while queued is used; a trashed item is skipped)."""
    note_ids = [r["id"] for r in refs if r["kind"] == "note"]
    mark_ids = [r["id"] for r in refs if r["kind"] == "highlight"]
    notes = {str(n.id): n for n in Note.objects.filter(pk__in=note_ids, user_id=user_id, deleted_at__isnull=True)}
    marks = {
        str(a.id): a
        for a in Annotation.objects.filter(
            pk__in=mark_ids, user_id=user_id, deleted_at__isnull=True, document__deleted_at__isnull=True
        ).select_related("document")
    }
    items: list[sdomain.SummaryItem] = []
    for r in refs:
        row = notes.get(r["id"]) if r["kind"] == "note" else marks.get(r["id"])
        if row is None:
            continue
        item = (_note_item if r["kind"] == "note" else _highlight_item)(len(items) + 1, row)
        if item:
            items.append(item)
    return items


# --- The request ---------------------------------------------------------------------------------------------------------
def _quota_error(user_id, exc: QuotaExceeded, now: datetime) -> QuotaExceeded:
    return QuotaExceeded(extra={**(exc.extra or {}), "kind": "ai_summaries", "resets_on": resets_on(now).isoformat()})


def _cached(user_id, input_hash: str, now: datetime) -> AiJob | None:
    return (
        AiJob.objects.filter(
            user_id=user_id,
            kind=AiJob.Kind.EXAM_SUMMARY,
            input_hash=input_hash,
            status__in=["ready", "accepted"],
            created_at__gte=now - timedelta(hours=CACHE_HOURS),
        )
        .order_by("-created_at")
        .first()
    )


def _active_for(user_id, chapter_id) -> AiJob | None:
    return AiJob.objects.filter(
        user_id=user_id, kind=AiJob.Kind.EXAM_SUMMARY, status__in=AiJob.ACTIVE, scope__chapter_id=str(chapter_id)
    ).first()


def request_summary(
    user_id, *, client_id, chapter_id, include: Iterable[str] = INCLUDE, now: datetime | None = None
) -> SummaryRequest:
    now = now or timezone.now()
    replay = AiJob.objects.filter(user_id=user_id, client_id=client_id).first()
    if replay is not None:
        return SummaryRequest(replay, False, False, 0)
    ai_gate.require("summary")
    ai_consent.require(user_id)
    link = links.link_columns(chapter_id)
    items, truncated = sdomain.cap_items(gather(user_id, link, include))
    if not sdomain.enough(items):
        raise NotEnoughMaterial(
            extra={
                "items": len(items),
                "chars": sum(len(i.text) for i in items),
                "min_items": sdomain.MIN_ITEMS,
                "min_chars": sdomain.MIN_CHARS,
            }
        )
    estimate = sdomain.estimate_seconds(items)
    input_hash = sdomain.input_hash(items, settings.GEMINI_MODEL)
    hit = _cached(user_id, input_hash, now)
    if hit is not None:
        return SummaryRequest(hit, False, True, 0)
    busy = _active_for(user_id, chapter_id)
    if busy is not None:
        return SummaryRequest(busy, False, False, estimate)
    ai_gate.check_budget("exam_summary", now)
    scope = {
        "chapter_id": str(chapter_id),
        "level_id": str(link["level_id"]),
        "subject_key": link["subject_key"],
        "chapter_key": link["chapter_key"],
        "include": sorted(set(include) & set(INCLUDE)),
        "items": [{"kind": i.kind, "id": i.id} for i in items],
        "truncated": truncated,
    }
    try:
        with transaction.atomic():
            try:
                quota.charge_monthly(user_id, "ai_summaries", 1, now=now)
            except QuotaExceeded as exc:
                raise _quota_error(user_id, exc, now) from exc
            job = AiJob.objects.create(
                user_id=user_id,
                client_id=client_id,
                kind=AiJob.Kind.EXAM_SUMMARY,
                scope=scope,
                input_hash=input_hash,
                model=settings.GEMINI_MODEL,
                prompt_version=sdomain.PROMPT_VERSION,
                item_count=len(items),
            )
            core_jobs.enqueue(
                JOB_SUMMARIZE,
                {"job_id": str(job.id)},
                dedupe_key=f"{JOB_SUMMARIZE}:{job.id}",
                max_attempts=MAX_ATTEMPTS,
            )
    except IntegrityError:  # the same client_id raced us; the charge rolled back with the transaction
        replay = AiJob.objects.filter(user_id=user_id, client_id=client_id).first()
        if replay is None:
            raise
        return SummaryRequest(replay, False, False, 0)
    return SummaryRequest(job, True, False, estimate)


# --- The worker ----------------------------------------------------------------------------------------------------------
def _last_attempt() -> bool:
    job = core_jobs.current_job()
    return job is not None and job.attempts >= job.max_attempts


def run_summary(payload: dict) -> dict:
    """
    Worker handler for `notes.summarize`. Re-checks everything that can change between the request and now (AI available,
    consent still given), calls Gemini once, validates the answer, stores the draft. Failure and block refund the quota.
    A network error is retried by the queue (once); on the last attempt the job is closed and refunded.
    """
    job_id = payload["job_id"]
    with transaction.atomic():
        job = AiJob.objects.select_for_update().filter(pk=job_id).first()
        if job is None or job.status not in (AiJob.Status.QUEUED, AiJob.Status.RUNNING):
            return {"skipped": True}
        if ai_gate.unavailable_reason("summary") is not None:
            ai_jobs.close(job, AiJob.Status.CANCELLED, error="unavailable", refunded=True)
            return {"status": "cancelled", "reason": "unavailable"}
        if not ai_consent.has_consent(job.user_id):
            ai_jobs.close(job, AiJob.Status.CANCELLED, error="consent_withdrawn", refunded=True)
            return {"status": "cancelled", "reason": "consent_withdrawn"}
        items = gather_by_ids(job.user_id, job.scope.get("items") or [])
        if not sdomain.enough(items):
            ai_jobs.close(job, AiJob.Status.FAILED, error="too_little", refunded=True)
            return {"status": "failed", "reason": "too_little"}
        if job.status == AiJob.Status.QUEUED:
            job.status, job.started_at = AiJob.Status.RUNNING, timezone.now()
            job.save(update_fields=["status", "started_at", "updated_at"])
    try:
        result = gemini.generate_structured(
            sdomain.build_prompt(items),
            system=sdomain.SYSTEM,
            schema=sdomain.RESPONSE_SCHEMA,
            max_output_tokens=sdomain.MAX_OUTPUT_TOKENS,
        )
        core_jobs.heartbeat()
        draft = sdomain.parse_output(result.text, items)
    except gemini.GeminiBlocked:
        return _fail(job_id, "blocked")
    except sdomain.BadOutput as exc:
        return _fail(job_id, exc.code)
    except (gemini.GeminiError, gemini.GeminiNotConfigured):
        if _last_attempt():
            return _fail(job_id, "model_error")
        raise
    return _store(job_id, result, draft, len(items))


def _fail(job_id, code: str) -> dict:
    with transaction.atomic():
        job = AiJob.objects.select_for_update().get(pk=job_id)
        if job.status in AiJob.ACTIVE:
            ai_jobs.close(job, AiJob.Status.FAILED, error=code, refunded=True)
    return {"status": "failed", "reason": code}


def _store(job_id, result: gemini.GeminiResult, draft: sdomain.Draft, item_count: int) -> dict:
    now = timezone.now()
    cost = sdomain.cost_paise(
        result.input_tokens,
        result.output_tokens,
        settings.GEMINI_PRICE_IN_PAISE_PER_M,
        settings.GEMINI_PRICE_OUT_PAISE_PER_M,
    )
    with transaction.atomic():
        job = AiJob.objects.select_for_update().get(pk=job_id)
        if job.status not in AiJob.ACTIVE:
            return {"status": job.status}
        job.input_tokens, job.output_tokens, job.cost_paise, job.model = (
            result.input_tokens,
            result.output_tokens,
            cost,
            result.model,
        )
        if not ai_consent.has_consent(job.user_id):  # withdrawn while the model was thinking: keep nothing
            ai_jobs.close(job, AiJob.Status.CANCELLED, error="consent_withdrawn", refunded=True, now=now)
            return {"status": "cancelled", "reason": "consent_withdrawn"}
        job.result_md = draft.markdown
        job.result_json = {
            "title": draft.title,
            "sources": draft.sources,
            "dropped": draft.dropped,
            "points": draft.points,
        }
        job.status, job.finished_at, job.expires_at, job.error_code = (
            AiJob.Status.READY,
            now,
            now + timedelta(days=sdomain.DRAFT_DAYS),
            None,
        )
        job.item_count = item_count
        job.save()
        events.announce_summary_ready(job.user_id, job.id, items=item_count, cost_paise=cost)
    return {"status": "ready", "points": draft.points, "cost_paise": cost}


def give_up(payload: dict) -> None:
    """The queue closed the job because workers kept going silent: close the record and refund."""
    with transaction.atomic():
        job = AiJob.objects.select_for_update().filter(pk=payload.get("job_id")).first()
        if job is not None and job.status in AiJob.ACTIVE:
            ai_jobs.close(job, AiJob.Status.FAILED, error="model_error", refunded=True)


# --- Review: accept ------------------------------------------------------------------------------------------------------
def accept_summary(user_id, job_id, *, body_md: str | None = None, title: str | None = None) -> tuple[AiJob, Note]:
    """
    Creates the note (kind `exam_summary`, origin `ai_summary`, one current per chapter) from the draft or the student's edit.
    Idempotent: an accepted job returns its note. 404 for another student's job, 409 `not_ready` unless the draft is ready.
    The note counts against the student's note quota like any note (429 `quota_exceeded`).
    """
    with transaction.atomic():
        job = ai_jobs.lock(user_id, job_id)
        if job is None or job.kind != AiJob.Kind.EXAM_SUMMARY:
            raise NotFound("Summary not found.")
        if job.status == AiJob.Status.ACCEPTED and job.result_note_id:
            note = Note.objects.filter(pk=job.result_note_id, user_id=user_id).first()
            if note is not None:
                return job, note
            raise NotFound("Summary not found.")
        if job.status != AiJob.Status.READY or job.result_md is None:
            raise DraftNotReady
        meta = job.result_json or {}
        chapter_id = uuid.UUID(job.scope["chapter_id"])
        final_title = (title or meta.get("title") or "Exam summary").strip()
        created = note_services.create_note(
            user_id,
            client_id=job.client_id,
            title=final_title,
            body_md=body_md if body_md is not None else job.result_md,
            chapter_id=chapter_id,
            origin=Note.Origin.AI_SUMMARY,
        )
        note = created.note
        keys = {"level_id": note.level_id, "subject_key": note.subject_key, "chapter_key": note.chapter_key}
        Note.objects.filter(user_id=user_id, is_current_summary=True, deleted_at__isnull=True, **keys).exclude(
            pk=note.pk
        ).update(is_current_summary=False)
        Note.objects.filter(pk=note.pk).update(
            kind=Note.Kind.EXAM_SUMMARY,
            is_current_summary=True,
            ai_job_id=job.id,
            source_refs=[
                {"type": s["kind"], "id": s["id"], "page": s["page"], "document_id": s.get("document_id")}
                for s in meta.get("sources", [])
            ],
        )
        job.result_note_id = note.id
        ai_jobs.close(job, AiJob.Status.ACCEPTED)
        note.refresh_from_db()
        return job, note


def disclosure() -> dict:
    return {"consent_version": consent_text.VERSION, "prompt_version": sdomain.PROMPT_VERSION}
