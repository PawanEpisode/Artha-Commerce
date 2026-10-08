"""
Unlock for search (PRD FR-F03-48): the student types the password of a locked PDF and its text becomes searchable.

What happens to the password
- It travels once, over TLS, in the request body, and is never logged (the views' bodies are scrubbed from Sentry).
- The API seals it with Fernet (`NOTES_UNLOCK_FERNET_KEYS`; no key, no feature) into the job's payload. The token itself
  expires after one hour (Fernet's own timestamp), and the worker clears it from the row the moment the job ends.
- The worker opens the PDF with it in memory, reads the text, and forgets it. No unprotected copy of the file is made.
- A light job (`notes.expire_unlock`) clears any token that outlived its hour, whatever happened to its job.

What is stored
- The text, on a PRIVATE `FileContent` of this document. Files are shared between students by their hash, and the text of a
  password-protected file must not become searchable for someone who has the same bytes but not the password.
- A PDF whose owner forbids copying text (`can_copy` false) is refused: the password opens the file for reading, not for extraction.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
import time
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core import jobs as core_jobs
from core.models import Job

from .. import events
from ..errors_unlock import NotLocked, TooManyAttempts, UnlockBusy, UnlockUnavailable
from ..models import Document, FileContent
from . import content as content_service
from . import documents, file_pages, objects, search_index

logger = logging.getLogger(__name__)

JOB_UNLOCK = "notes.unlock"
TOKEN_TTL_SECONDS = 3600
MAX_FAILURES = 5
LOCKOUT = timedelta(hours=1)
BUDGET_SECONDS = 150  # one job's share; the rest of a long file is a new job
CHUNK_PAGES = 20
MAX_PASSWORD = 256
FAILURES = ("wrong_password", "restricted", "unreadable", "expired")


# --- Sealing ----------------------------------------------------------------------------------------------------------------
def _fernet() -> MultiFernet:
    keys = [k.strip() for k in (getattr(settings, "NOTES_UNLOCK_FERNET_KEYS", "") or "").split(",") if k.strip()]
    try:
        return MultiFernet([Fernet(k) for k in keys])
    except (ValueError, TypeError):  # empty list or a malformed key: the feature stays off rather than weaken anything
        raise UnlockUnavailable from None


def seal(password: str) -> str:
    return _fernet().encrypt(password.encode()).decode()


def unseal(token: str) -> str | None:
    """The password, or None when the token is too old or not ours. Never raises with the token in the message."""
    try:
        return _fernet().decrypt(token.encode(), ttl=TOKEN_TTL_SECONDS).decode()
    except (InvalidToken, UnicodeError, UnlockUnavailable):  # no key any more: the secret cannot be read, so it is gone
        return None


def available() -> bool:
    try:
        _fernet()
    except UnlockUnavailable:
        return False
    return True


def private_sha(document_id) -> str:
    """The hash of this document's own `FileContent`: never equal to the hash of real bytes, so no upload ever reuses it."""
    return hashlib.sha256(f"notes.unlock:{document_id}".encode()).hexdigest()


# --- The request ------------------------------------------------------------------------------------------------------------
def request_unlock(user_id, document_id, password: str) -> Document:
    """
    Queues the reading of a locked PDF. 404 for another student's, 409 `not_locked` / `unlock_in_progress`, 429
    `too_many_attempts` after five wrong passwords in an hour, 503 `unlock_unavailable` without a key.
    """
    token = seal(password)  # first: no key, no work, and nothing about the document is revealed
    with transaction.atomic():
        document = documents.get_locked(user_id, document_id)
        if document.deleted_at is not None or document.status != Document.Status.NEEDS_PASSWORD:
            raise NotLocked
        if document.unlock_status in ("waiting", "running"):
            raise UnlockBusy
        now = timezone.now()
        recent = document.unlock_failed_at is not None and now - document.unlock_failed_at < LOCKOUT
        if recent and document.unlock_failures >= MAX_FAILURES:
            raise TooManyAttempts
        if not recent:
            document.unlock_failures = 0
        document.unlock_status, document.unlock_reason = "waiting", None
        document.save(update_fields=["unlock_status", "unlock_reason", "unlock_failures", "updated_at"])
        core_jobs.enqueue(
            JOB_UNLOCK,
            {"document_id": str(document.id), "secret": token},
            dedupe_key=f"{JOB_UNLOCK}:{document.id}",
            max_attempts=3,
        )
    return document


# --- The job ----------------------------------------------------------------------------------------------------------------
def _scrub(job: Job | None) -> None:
    """The password's token leaves the row. A queryset update, so the queue's own saves cannot put it back."""
    if job is not None:
        payload = {k: v for k, v in (job.payload or {}).items() if k != "secret"}
        Job.objects.filter(pk=job.pk).update(payload=payload)


def _fail(document_id, reason: str) -> None:
    now = timezone.now()
    wrong = reason == "wrong_password"
    rows = Document.objects.filter(pk=document_id)
    rows.update(unlock_status="failed", unlock_reason=reason, updated_at=now)
    if wrong:
        from django.db.models import F

        rows.update(unlock_failures=F("unlock_failures") + 1, unlock_failed_at=now)


def run_unlock(payload: dict) -> dict:
    """Worker handler for `notes.unlock`. Answers with a code and counts only, never the password or any text."""
    job = core_jobs.current_job()
    try:
        outcome = _run(payload, job)
    except Exception:
        if job is not None and job.attempts >= job.max_attempts:
            _fail(payload.get("document_id"), "unreadable")
            _scrub(job)
        raise  # an earlier attempt keeps the token for the retry; the error text never carries it
    _scrub(job)
    return outcome


def _run(payload: dict, job: Job | None) -> dict:
    from ..worker import extract, pdfutil
    from ..worker import inspect as pdf_inspect

    document = Document.objects.select_related("attachment", "content").filter(pk=payload.get("document_id")).first()
    if document is None or document.deleted_at is not None:
        return {"skipped": "gone"}
    if document.unlock_status not in ("waiting", "running"):
        return {"skipped": "changed"}
    password = unseal(payload.get("secret") or "")
    if password is None:
        _fail(document.id, "expired")
        return {"failed": "expired"}
    Document.objects.filter(pk=document.pk).update(unlock_status="running", updated_at=timezone.now())

    with tempfile.TemporaryDirectory(prefix="unlock-") as tmp:
        path = os.path.join(tmp, "source.pdf")
        objects.download_to(path, document.attachment, limit=document.bytes)
        if document.status == Document.Status.NEEDS_PASSWORD:
            result = pdf_inspect.inspect_pdf(path, password=password)
            if result.needs_password:
                _fail(document.id, "wrong_password")
                return {"failed": "wrong_password"}
            if not result.ok or not result.page_count:
                _fail(document.id, "unreadable")
                return {"failed": "unreadable"}
            if result.can_copy is False:
                _fail(document.id, "restricted")
                return {"failed": "restricted"}
            content = _adopt(document, result)
        else:
            content = document.content
        start = int(payload.get("from") or content.text_pages_done + 1)
        return _read(document, content, path, password, start, payload, extract, pdfutil)


def _adopt(document: Document, result) -> FileContent:
    """The document now has its own content row: page facts known, text to come. The shared locked row is let go."""
    with transaction.atomic():
        document = Document.objects.select_for_update().get(pk=document.pk)
        old_content_id = document.content_id
        content, _ = FileContent.objects.get_or_create(
            sha256=private_sha(document.id), defaults={"bytes": result.bytes or document.bytes}
        )
        content.is_encrypted = True
        content.page_count, content.page_meta = result.page_count, list(result.page_meta)
        content.outline = list(result.outline)
        content.can_copy, content.can_modify = result.can_copy, result.can_modify
        content.has_javascript = result.has_javascript
        content.is_scanned, content.text_pct = result.is_scanned, result.text_pct
        content.text_status = FileContent.TextStatus.RUNNING
        content.save()
        document.content, document.page_count = content, content.page_count
        document.status, document.status_reason = Document.Status.READY, None
        document.save(update_fields=["content", "page_count", "status", "status_reason", "updated_at"])
    content_service.mark_orphaned([old_content_id])
    events.announce_document_ready(
        document.user_id,
        document.id,
        pages=content.page_count,
        scanned=content.is_scanned,
        encrypted=True,
        stage="readable",
    )
    return content


def _read(document, content, path, password, start, payload, extract, pdfutil) -> dict:
    deadline = time.monotonic() + BUDGET_SECONDS
    page, total = start, content.page_count
    while page <= total:
        last = min(page + CHUNK_PAGES - 1, total)
        try:
            pages = extract.extract_pages(path, page, last, password=password)
        except pdfutil.PdfPasswordRequired:
            _fail(document.id, "wrong_password")
            return {"failed": "wrong_password"}
        except pdfutil.PdfOpenError:
            _fail(document.id, "unreadable")
            return {"failed": "unreadable"}
        writes = [file_pages.PageWrite(p.page, p.text) for p in pages]
        file_pages.upsert_pages(content.pk, writes)
        search_index.refresh_pages(content.pk, [w.page for w in writes])
        file_pages.record_text_progress(content.pk, last)
        if not core_jobs.heartbeat() and core_jobs.current_job() is not None:
            return {"stopped": "lock lost", "reached": last}
        page = last + 1
        if page <= total and time.monotonic() > deadline:
            core_jobs.enqueue(
                JOB_UNLOCK,
                {"document_id": str(document.id), "secret": payload.get("secret"), "from": page},
                dedupe_key=f"{JOB_UNLOCK}:{document.id}:{page}",
                max_attempts=3,
            )
            return {"chained": page}
    FileContent.objects.filter(pk=content.pk).update(text_status="done", updated_at=timezone.now())
    Document.objects.filter(pk=document.pk).update(unlock_status="done", unlock_reason=None, unlock_failures=0)
    events.announce_document_ready(
        document.user_id, document.id, pages=total, scanned=content.is_scanned, encrypted=True, stage="searchable"
    )
    return {"done": True, "pages": total}


def give_up(payload: dict) -> None:
    """The queue gave up on a silent worker: say so, and make sure the token is gone."""
    _fail(payload.get("document_id"), "unreadable")
    Job.objects.filter(type=JOB_UNLOCK, dedupe_key=f"{JOB_UNLOCK}:{payload.get('document_id')}").update(
        payload={"document_id": payload.get("document_id")}
    )


def expire_secrets(now=None) -> int:
    """Clears every password token older than its hour from the queue, whatever became of its job. Returns how many."""
    cutoff = (now or timezone.now()) - timedelta(seconds=TOKEN_TTL_SECONDS)
    cleared = 0
    for job in Job.objects.filter(type=JOB_UNLOCK, created_at__lt=cutoff, payload__has_key="secret").iterator():
        _scrub(job)
        cleared += 1
        Document.objects.filter(
            pk=(job.payload or {}).get("document_id"), unlock_status__in=["waiting", "running"]
        ).update(unlock_status="failed", unlock_reason="expired", updated_at=timezone.now())
    return cleared
