"""
AI page reading ("Improve this page", PRD FR-F03-52): the request a paying student makes and the job the worker runs.

The rules this rests on
- It is asked for per page (up to 10 a request) and never automatic. Tesseract stays the default for everyone; AI is the paid
  upgrade for pages it read badly or that are handwritten. The picture of each page goes to Google only after the student
  agreed (`ai_consent`), and only while AI is switched on (`ai_gate`): both are checked in the request and again before every page.
- The price is the pages: `ai_ocr_pages` is charged for the pages that need work, in the transaction that creates the job
  (the free plan has 0, so it is refused with 429 `quota_exceeded`). A page that could not be read is given back, one page at
  a time, as soon as that is known. A finished job holds exactly the pages it read.
- A page already read by AI, one with its own text layer (20 characters or more) and one that another active job of the same
  file will read is skipped and not charged. Rank is `native < ocr < ai`, so the result replaces Tesseract text and is never
  replaced by it (`file_pages.upsert_pages`).
- The job row keeps numbers and page numbers only: `scope {document_id, content_id, pages, refunded_pages}` and
  `result_json {done: {page: legibility}, failed: {page: code}}`. The text lives in `FilePage` like any other page text.
- Resumable: a retry reads only the pages not yet in `done` or `failed`.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import jobs as core_jobs
from integrations import gemini

from ..domain import ai_ocr as domain
from ..domain import summary as sdomain
from ..domain.pagespec import PageSpecError, format_pages, parse_pages
from ..errors import QuotaExceeded
from ..errors_ocr_export import InvalidPages, NotScannedOrNoPages
from ..models import AiJob, Document, FileContent, FilePage
from . import ai_consent, ai_gate, ai_jobs, file_pages, objects, ocr, quota, search_index

logger = logging.getLogger(__name__)

JOB_OCR_AI = "notes.ocr_ai"
MAX_ATTEMPTS = 2


@dataclass(frozen=True)
class AiOcrRequest:
    job: AiJob | None
    charged_pages: int
    skipped: dict  # {"already_read": [pages], "has_text": [pages], "in_progress": [pages]}
    estimate_seconds: int


def _active_pages(content_id) -> set[int]:
    out: set[int] = set()
    for scope in AiJob.objects.filter(
        kind=AiJob.Kind.OCR_PAGE_AI, status__in=AiJob.ACTIVE, scope__content_id=str(content_id)
    ).values_list("scope", flat=True):
        out.update(set(scope.get("pages") or []) - set(scope.get("refunded_pages") or []))
    return out


def request_ai_ocr(user_id, document_id, *, pages: str | None, now: datetime | None = None) -> AiOcrRequest:
    """
    Raises 503 `ai_unavailable` / `ai_budget_exhausted`, 403 `ai_not_consented`, 404, 409 `locked` / `not_ready`, 422
    `invalid_pages` (also: more than 10 pages) / `not_scanned_or_no_pages` / `ocr_not_allowed`, 429 `quota_exceeded` kind `ai_ocr_pages`.
    """
    now = now or timezone.now()
    ai_gate.require("ocr")
    ai_consent.require(user_id)
    document = Document.objects.filter(pk=document_id, user_id=user_id, deleted_at__isnull=True).first()
    if document is None:
        raise NotFound("Document not found.")
    with transaction.atomic():
        content = FileContent.objects.select_for_update().filter(pk=document.content_id).first()
        content = ocr._check_openable(
            document, content
        )  # same refusals as Tesseract: locked, not ready, copying not allowed
        try:
            requested = parse_pages(pages, content.page_count)
        except PageSpecError as exc:
            raise InvalidPages(str(exc), extra={"reason": exc.code}) from exc
        if not pages or len(requested) > domain.MAX_PAGES:
            raise InvalidPages(
                f"Pick up to {domain.MAX_PAGES} pages at a time.", extra={"reason": "too_many", "max": domain.MAX_PAGES}
            )
        have = {
            p: (src, text)
            for p, src, text in FilePage.objects.filter(content=content, page__in=requested).values_list(
                "page", "text_source", "text"
            )
        }
        busy = _active_pages(content.id)
        skipped: dict[str, list[int]] = {"already_read": [], "has_text": [], "in_progress": []}
        needed: list[int] = []
        for page in requested:
            src, text = have.get(page, ("", ""))
            if src == "ai":
                skipped["already_read"].append(page)
            elif domain.native_covers(src, text):
                skipped["has_text"].append(page)
            elif page in busy:
                skipped["in_progress"].append(page)
            else:
                needed.append(page)
        if not needed:
            if skipped["in_progress"] or skipped["already_read"]:
                return AiOcrRequest(None, 0, skipped, 0)
            raise NotScannedOrNoPages
        ai_gate.check_budget("ocr_page_ai", now)
        try:
            quota.charge_monthly(user_id, "ai_ocr_pages", len(needed), now=now)
        except QuotaExceeded as exc:
            from ..domain.quota import resets_on

            raise QuotaExceeded(
                extra={**(exc.extra or {}), "kind": "ai_ocr_pages", "resets_on": resets_on(now).isoformat()}
            ) from exc
        job = AiJob.objects.create(
            user_id=user_id,
            client_id=uuid.uuid4(),
            kind=AiJob.Kind.OCR_PAGE_AI,
            scope={
                "document_id": str(document.id),
                "content_id": str(content.id),
                "pages": needed,
                "refunded_pages": [],
            },
            input_hash=domain.input_hash(content.id, needed, settings.GEMINI_MODEL),
            model=settings.GEMINI_MODEL,
            prompt_version=domain.PROMPT_VERSION,
            item_count=len(needed),
            result_json={"done": {}, "failed": {}},
        )
        core_jobs.enqueue(
            JOB_OCR_AI,
            {"job_id": str(job.id)},
            dedupe_key=f"{JOB_OCR_AI}:{job.id}",
            max_attempts=MAX_ATTEMPTS,
        )
    return AiOcrRequest(job, len(needed), skipped, domain.estimate_seconds(len(needed)))


# --- The worker ----------------------------------------------------------------------------------------------------------
def _last_attempt() -> bool:
    job = core_jobs.current_job()
    return job is not None and job.attempts >= job.max_attempts


def _progress(job: AiJob) -> tuple[dict, dict]:
    data = job.result_json or {}
    return dict(data.get("done") or {}), dict(data.get("failed") or {})


def _left(job: AiJob) -> list[int]:
    done, failed = _progress(job)
    return [p for p in job.scope.get("pages") or [] if str(p) not in done and str(p) not in failed]


def _stop_reason() -> str | None:
    return "unavailable" if ai_gate.unavailable_reason("ocr") is not None else None


def run_ai_ocr(payload: dict) -> dict:
    """
    Worker handler for `notes.ocr_ai`: reads the pages not yet read, one Gemini call each, saving after every page. AI turned
    off or consent withdrawn stops the job and gives back the pages not yet read. A failing page is given back and skipped;
    a network error is retried by the queue (progress is kept) and on the last attempt gives back what is left.
    """
    job_id = payload["job_id"]
    with transaction.atomic():
        job = AiJob.objects.select_for_update().filter(pk=job_id).first()
        if job is None or job.status not in AiJob.ACTIVE:
            return {"skipped": True}
        if job.status == AiJob.Status.QUEUED:
            job.status, job.started_at = AiJob.Status.RUNNING, timezone.now()
            job.save(update_fields=["status", "started_at", "updated_at"])
        content_id = job.scope["content_id"]
        left = _left(job)
    content = FileContent.objects.filter(pk=content_id).first()
    attachment = ocr._source_attachment(content, job.scope.get("document_id")) if content else None
    if content is None or attachment is None:
        return _finish(job_id, stop_code="model_error")
    from ..worker import page_image  # lazy: PDFium is a worker library

    with tempfile.TemporaryDirectory(prefix="aiocr-") as tmp:
        source = os.path.join(tmp, "source.pdf")
        objects.download_to(source, attachment, limit=content.bytes)
        for page in left:
            stop = _check_open(job_id)
            if stop:
                return _finish(job_id, stop_code=stop)
            outcome = _read_page(job_id, content, source, page, page_image)
            if outcome == "retry":
                if _last_attempt():
                    return _finish(job_id, stop_code="model_error")
                raise gemini.GeminiError("Gemini call failed; the queue will retry.")
            core_jobs.heartbeat()
    return _finish(job_id)


def _check_open(job_id) -> str | None:
    """Between pages: still active, still allowed, still consented. Returns the code to stop with, or None to go on."""
    job = AiJob.objects.filter(pk=job_id).only("status", "user_id").first()
    if job is None or job.status not in AiJob.ACTIVE:
        return "cancelled"
    if _stop_reason() is not None:
        return "unavailable"
    if not ai_consent.has_consent(job.user_id):
        return "consent_withdrawn"
    return None


def _read_page(job_id, content, source: str, page: int, page_image) -> str:
    """Reads one page and records it. Returns `done`, `failed` or `retry` (a transient error: nothing recorded)."""
    try:
        image = page_image.render_page_jpeg(source, page)
    except page_image.PageImageError as exc:
        _record(job_id, page, failed=str(exc))
        return "failed"
    try:
        result = gemini.generate_structured(
            domain.PROMPT,
            system=domain.SYSTEM,
            schema=domain.SCHEMA,
            max_output_tokens=domain.MAX_OUTPUT_TOKENS,
            image=(image, page_image.MIME),
        )
    except gemini.GeminiBlocked:
        _record(job_id, page, failed="blocked")
        return "failed"
    except (gemini.GeminiError, gemini.GeminiNotConfigured):
        return "retry"
    try:
        read = domain.parse_output(result.text)
    except domain.Unreadable as exc:
        _record(job_id, page, failed=exc.code, tokens=result)
        return "failed"
    with transaction.atomic():
        job = AiJob.objects.select_for_update().get(pk=job_id)
        if job.status not in AiJob.ACTIVE or not ai_consent.has_consent(job.user_id):
            return "failed"  # withdrawn while the model was reading: keep nothing
        file_pages.upsert_pages(content.id, [file_pages.PageWrite(page, read.text, "ai", read.conf, None)])
        _save(job, page, done=read.legibility, tokens=result)
    search_index.refresh_pages(content.id, [page])
    return "done"


def _record(job_id, page: int, *, failed: str, tokens=None) -> None:
    with transaction.atomic():
        job = AiJob.objects.select_for_update().get(pk=job_id)
        if job.status in AiJob.ACTIVE:
            ai_jobs.refund_pages(job, [page])
            _save(job, page, failed=failed, tokens=tokens)


def _save(job: AiJob, page: int, *, done: str | None = None, failed: str | None = None, tokens=None) -> None:
    data = job.result_json or {"done": {}, "failed": {}}
    if done:
        data["done"][str(page)] = done
    if failed:
        data["failed"][str(page)] = failed
    job.result_json = data
    if tokens is not None:
        job.input_tokens += tokens.input_tokens
        job.output_tokens += tokens.output_tokens
        job.model = tokens.model
    job.save()


def _finish(job_id, *, stop_code: str | None = None) -> dict:
    """Ends the job. Pages not read are given back. `accepted` when at least one page was stored, else `failed`/`cancelled`."""
    now = timezone.now()
    content_id = None
    with transaction.atomic():
        job = AiJob.objects.select_for_update().get(pk=job_id)
        if job.status not in AiJob.ACTIVE:
            return {"status": job.status}
        left = _left(job)
        if left:
            ai_jobs.refund_pages(job, left)
            data = job.result_json or {"done": {}, "failed": {}}
            data["failed"].update({str(p): stop_code or "model_error" for p in left})
            job.result_json = data
        done, _ = _progress(job)
        job.cost_paise = sdomain.cost_paise(
            job.input_tokens,
            job.output_tokens,
            settings.GEMINI_PRICE_IN_PAISE_PER_M,
            settings.GEMINI_PRICE_OUT_PAISE_PER_M,
        )
        job.finished_at = now
        if done:
            job.status, job.error_code = AiJob.Status.ACCEPTED, None
            content_id = job.scope["content_id"]
        else:
            job.status = (
                AiJob.Status.CANCELLED if stop_code in ("consent_withdrawn", "unavailable") else AiJob.Status.FAILED
            )
            job.error_code = stop_code or _dominant_failure(job)
        if len(job.scope.get("refunded_pages") or []) >= len(job.scope.get("pages") or []):
            job.charged = False
        job.save()
    if content_id:
        ocr.announce_searchable(content_id)
    return {"status": job.status, "pages_read": len(done)}


def _dominant_failure(job: AiJob) -> str:
    codes = list((job.result_json or {}).get("failed", {}).values())
    if "blocked" in codes:
        return "blocked"
    if "illegible" in codes:
        return "too_little"  # the column's own code for "nothing usable came back"
    return "model_error"


def give_up(payload: dict) -> None:
    """The queue closed the job because workers kept going silent: give back what was not read."""
    with transaction.atomic():
        job = AiJob.objects.select_for_update().filter(pk=payload.get("job_id")).first()
        active = job is not None and job.status in AiJob.ACTIVE
    if active:
        _finish(payload["job_id"], stop_code="model_error")


def summary_of(job: AiJob) -> dict:
    """`{pages, done: {page: legibility}, failed: {page: code}, refunded_pages}` for the answer (never any text)."""
    done, failed = _progress(job)
    return {
        "pages": job.scope.get("pages") or [],
        "done": {int(k): v for k, v in done.items()},
        "failed": {int(k): v for k, v in failed.items()},
        "refunded_pages": job.scope.get("refunded_pages") or [],
        "spec": format_pages(job.scope.get("pages") or []) if job.scope.get("pages") else "",
    }
