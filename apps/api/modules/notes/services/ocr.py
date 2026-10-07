"""
OCR of scanned PDFs (PRD FR-F03-49 to 51, ERD 2.2, 2.3, 6.5): the request a student makes and the chunk the worker runs.

Facts the design rests on
- The derived rows belong to `FileContent`, so every document of identical bytes sees them and a page is OCR'd once.
- Progress lives in the ROWS (`FilePage` with `text_source = 'ocr'`), never in the process: a chunk looks at which pages of its
  page selection have no OCR text yet and does the next ten. A worker that dies at page 120 therefore resumes at 121.
- A page that already has native text (20 characters or more) or AI text is never overwritten ("never downgrade"), and a page
  that already has OCR text from the same engine is not read again (an OCR rerun is a no-op).
- The student's monthly `ocr_pages` is charged for the pages that really need work and are not already queued by an earlier
  request, in the same transaction that queues the job and under the content row's lock, so two requests can never both pass
  the last pages. A request whose pages are all done already (a second student with the same bytes) charges nothing: that is
  the "charged then refunded" rule of the ERD, in one step instead of two.

Engine string stored on the content: `tesseract-5.<engine_version>:<lang>`. `eng+hin` covers a later `eng` request; an `eng`
result does not cover `eng+hin`, so asking for Hindi redoes the pages read as English (and charges for them: the response
says how many) rather than leaving a content half in one language.

Job payload `notes.ocr`: `{content_id, document_id, user_id, spec, lang, since, chain, charged, pages: [from, to]}`. `spec` is
the page selection this request needs ("1-40,50"), `pages` the chunk that was next when the job was queued (informational),
`since` an ISO time set only when the engine changed (pages OCR'd before it are stale), `charged` what the student paid.
Chain: the first job of a request has `dedupe_key = notes.ocr:<content_id>` (or `...:<chain>` when another request is
already running for that content); each chunk queues the next one as `notes.ocr:<content_id>:<chain>:<first page>`, because
the running job still holds its own key.
"""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone
from rest_framework.exceptions import NotFound

from core import jobs as core_jobs
from core.models import Job

from .. import events
from ..domain import ocr_quality
from ..domain.pagespec import PageSpecError, format_pages, parse_pages
from ..domain.quota import resets_on
from ..errors import NotesFeatureDisabled, QuotaExceeded
from ..errors_ocr_export import InvalidPages, Locked, NotReady, NotScannedOrNoPages, OcrNotAllowed
from ..models import Document, FileContent, FilePage, Settings
from . import file_pages, objects, quota, search_index

logger = logging.getLogger(__name__)

JOB_OCR = "notes.ocr"  # same string as `notes.jobs.JOB_OCR`; not imported because `notes.jobs` imports this package
CHUNK = (
    10  # pages per job; equals `worker.ocr.OCR_CHUNK` (a test pins it) without importing the worker's libraries here
)
LANGS = ("eng", "eng+hin")
ENGINE_FAMILY = "tesseract-5"
FIRST_CHUNK_PRIORITY = 10  # the first ten pages of every request are claimed before later chunks of any document
LATER_CHUNK_PRIORITY = 0
WAIT_STUDENT_SECONDS = 20  # one OCR document per student at a time
WAIT_CONTENT_SECONDS = 10  # one chain per file at a time
NATIVE_MIN_CHARS = ocr_quality.SCANNED_MAX_CHARS  # a page with this much native text is not a scan
# Pages whose problem is theirs alone: stored as empty OCR pages so the chain moves on. `ocr_failed` is the engine itself.
PAGE_ERRORS = frozenset({"page_too_large", "render_too_large", "render_failed", "timeout"})


@dataclass(frozen=True)
class OcrRequest:
    status: str  # pending | running | partial | done
    ocr_pages_total: int
    charged_pages: int
    estimate_seconds: int


# --- Pure helpers -------------------------------------------------------------------------------------------------------
def engine_string(lang: str, engine_version: int = 1) -> str:
    return f"{ENGINE_FAMILY}.{engine_version}:{lang}"


def engine_lang(engine: str | None) -> str | None:
    return engine.rsplit(":", 1)[1] if engine and ":" in engine else None


def engine_covers(engine: str | None, lang: str) -> bool:
    """True when text read by `engine` is as good as a read in `lang`: the same language, or English asked of English+Hindi."""
    done = engine_lang(engine)
    return done == lang or (done == "eng+hin" and lang == "eng")


def pages_of_spec(spec: str | None) -> list[int]:
    """The pages a stored spec names. A stored spec was validated at request time, so no page count is needed here."""
    if not spec:
        return []
    return parse_pages(spec, 100_000)


# --- Reading the state of a content -------------------------------------------------------------------------------------
def _ocr_pages_valid(content_id, *, since: datetime | None, lang: str, engine: str | None) -> set[int]:
    """Pages whose OCR text counts as current: written since the engine changed, else any OCR text when the engine covers `lang`."""
    rows = FilePage.objects.filter(content_id=content_id, text_source="ocr")
    if since is not None:
        rows = rows.filter(updated_at__gte=since)
    elif not engine_covers(engine, lang):
        return set()
    return set(rows.values_list("page", flat=True))


def _protected_pages(content_id) -> set[int]:
    """Pages OCR must not touch: native text of 20 characters or more, and any AI text."""
    out: set[int] = set()
    for page, source, length in (
        FilePage.objects.filter(content_id=content_id)
        .exclude(text_source="ocr")
        .values_list("page", "text_source", "text")
    ):
        if source == "ai" or len((length or "").strip()) >= NATIVE_MIN_CHARS:
            out.add(page)
    return out


def _queued_pages(content_id) -> set[int]:
    """Pages promised to jobs that are queued or running for this content (their `spec`), so a request is not charged twice."""
    out: set[int] = set()
    jobs = Job.objects.filter(
        type=JOB_OCR, dedupe_key__startswith=f"{JOB_OCR}:{content_id}", status__in=Job.ACTIVE_STATUSES
    )
    for payload in jobs.values_list("payload", flat=True):
        out.update(pages_of_spec(payload.get("spec")))
    return out


# --- The request --------------------------------------------------------------------------------------------------------
def _default_lang(user_id) -> str:
    lang = Settings.objects.filter(pk=user_id).values_list("ocr_lang", flat=True).first()
    return lang if lang in LANGS else "eng"


def _ocr_quota_error(user_id, exc: QuotaExceeded, now: datetime) -> QuotaExceeded:
    extra = {**(exc.extra or {}), "kind": "ocr", "resets_on": resets_on(now).isoformat()}
    return QuotaExceeded(extra=extra)


def _check_openable(document: Document, content: FileContent | None) -> FileContent:
    if document.status == "needs_password" or (
        content is not None and content.is_encrypted and content.page_count is None
    ):
        raise Locked
    if content is None or not content.page_count or document.status not in ("ready", "inspecting"):
        raise NotReady
    if content.can_copy is False:
        raise OcrNotAllowed
    return content


def request_ocr(
    user_id, document_id, *, mode: str = "tesseract", lang: str | None = None, pages: str | None = None, now=None
) -> OcrRequest:
    """
    Starts (or joins) OCR for the pages of a document that have no text. Raises 403 `feature_disabled` for `mode = "ai"` (R3),
    404, 409 `locked` / `not_ready`, 422 `invalid_pages` / `not_scanned_or_no_pages` / `ocr_not_allowed`, and 429
    `quota_exceeded` kind `ocr` with `{used, limit, plan, resets_on}`.
    """
    if mode != "tesseract":
        raise NotesFeatureDisabled
    now = now or timezone.now()
    lang = lang or _default_lang(user_id)
    if lang not in LANGS:
        raise InvalidPages("Unsupported language.")
    document = Document.objects.filter(pk=document_id, user_id=user_id, deleted_at__isnull=True).first()
    if document is None:
        raise NotFound("Document not found.")
    with transaction.atomic():
        content = FileContent.objects.select_for_update().filter(pk=document.content_id).first()
        content = _check_openable(document, content)
        try:
            requested = parse_pages(pages, content.page_count)
        except PageSpecError as exc:
            raise InvalidPages(str(exc), extra={"reason": exc.code}) from exc
        engine = engine_string(lang, content.engine_version)
        switching = bool(content.ocr_engine) and not engine_covers(content.ocr_engine, lang)
        has_ocr = content.ocr_pages_done > 0 or FilePage.objects.filter(content=content, text_source="ocr").exists()
        protected = _protected_pages(content.id)
        queued = _queued_pages(content.id)
        if switching and has_ocr:
            # The pages read as English are stale for Hindi: redo them together with what was asked for.
            stale = set(FilePage.objects.filter(content=content, text_source="ocr").values_list("page", flat=True))
            valid: set[int] = set()
            wanted = sorted((set(requested) | stale) - protected)
        else:
            valid = _ocr_pages_valid(content.id, since=None, lang=lang, engine=content.ocr_engine)
            wanted = [p for p in requested if p not in protected]
        if not wanted:
            raise NotScannedOrNoPages
        needed = [p for p in wanted if p not in valid and p not in queued]
        if not needed:
            result = _already_covered(document, content, lang, now)
        else:
            result = _queue(
                user_id,
                document,
                content,
                needed,
                lang,
                now,
                total=len(valid | queued | set(needed)),
                switched=switching and has_ocr,
                engine=engine,
            )
    if not needed and result.status == "done":
        _announce(document)  # after the transaction: a consumer must see the committed state
    return result


def _queue(user_id, document, content, needed, lang, now, *, total, switched, engine) -> OcrRequest:
    """Charges the pages and queues the first chunk. Runs inside the request's transaction, under the content row's lock."""
    try:
        quota.charge_monthly(user_id, "ocr_pages", len(needed), now=now)
    except QuotaExceeded as exc:
        raise _ocr_quota_error(user_id, exc, now) from exc
    updates = {"ocr_engine": engine, "ocr_pages_total": total, "updated_at": now}
    if switched:
        updates.update(ocr_pages_done=0, ocr_status="pending")
    elif content.ocr_status in ("none", "done", "failed"):
        updates["ocr_status"] = "pending"
    FileContent.objects.filter(pk=content.pk).update(**updates)
    Document.objects.filter(pk=document.pk).update(ocr_mode="tesseract", ocr_lang=lang, updated_at=now)
    _enqueue_first(content, document, user_id, needed, lang, since=now if switched else None)
    status = updates.get("ocr_status", content.ocr_status)
    return OcrRequest(status, total, len(needed), ocr_quality.ocr_estimate_seconds(len(needed)))


def _already_covered(document: Document, content: FileContent, lang: str, now: datetime) -> OcrRequest:
    """Every page asked for is read already or queued by someone: nothing to charge and nothing to queue."""
    Document.objects.filter(pk=document.pk).update(ocr_mode="tesseract", ocr_lang=lang, updated_at=now)
    status = content.ocr_status if content.ocr_status in ("pending", "running", "partial") else "done"
    return OcrRequest(status, content.ocr_pages_total, 0, 0)


def _enqueue_first(content: FileContent, document: Document, user_id, needed: list[int], lang: str, *, since) -> None:
    chain = uuid.uuid4().hex[:8]
    payload = {
        "content_id": str(content.id),
        "document_id": str(document.id),
        "user_id": str(user_id),
        "spec": format_pages(needed),
        "lang": lang,
        "since": since.isoformat() if since else None,
        "chain": chain,
        "charged": len(needed),
        "pages": [needed[0], needed[min(CHUNK, len(needed)) - 1]],
    }
    base = f"{JOB_OCR}:{content.id}"
    busy = Job.objects.filter(dedupe_key=base, status__in=Job.ACTIVE_STATUSES).exists()
    core_jobs.enqueue(JOB_OCR, payload, dedupe_key=f"{base}:{chain}" if busy else base, priority=FIRST_CHUNK_PRIORITY)


def _announce(document: Document) -> None:
    content = FileContent.objects.filter(pk=document.content_id).first()
    events.announce_document_ready(
        document.user_id,
        document.id,
        pages=content.page_count if content else None,
        scanned=content.is_scanned if content else None,
        encrypted=content.is_encrypted if content else False,
        stage="searchable",
    )


# --- The chunk (worker) -------------------------------------------------------------------------------------------------
def _parse_since(raw) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None


def _must_wait(content_id, user_id, me: Job | None) -> int:
    """Seconds to wait when this student already has another file's OCR running, or this file has another chain running."""
    running = Job.objects.filter(type=JOB_OCR, status=Job.Status.RUNNING)
    if me is not None:
        running = running.exclude(pk=me.pk)
    for payload in running.values_list("payload", flat=True):
        if payload.get("content_id") == str(content_id):
            return WAIT_CONTENT_SECONDS
        if payload.get("user_id") == str(user_id):
            return WAIT_STUDENT_SECONDS
    return 0


def _defer(payload: dict, seconds: int, me: Job | None) -> None:
    """The same work again a little later, as a new job (the running one completes). One waiting job per chain."""
    key = f"{JOB_OCR}:{payload['content_id']}:{payload.get('chain', 'x')}:w{uuid.uuid4().hex[:6]}"
    core_jobs.enqueue(
        JOB_OCR,
        payload,
        dedupe_key=key,
        run_after=timezone.now() + timedelta(seconds=seconds),
        priority=me.priority if me else LATER_CHUNK_PRIORITY,
    )


def _source_attachment(content: FileContent, document_id):
    """The stored original: the requesting document's file, else the file of any live document of the same bytes."""
    candidates = Document.objects.filter(content=content, deleted_at__isnull=True).exclude(
        status__in=["rejected", "expired", "failed", "reserved"]
    )
    ordered = sorted(candidates.select_related("attachment"), key=lambda d: str(d.id) != str(document_id))
    for document in ordered:
        if document.attachment.status == "clean":
            return document.attachment
    return None


def run_chunk(payload: dict) -> dict:
    """
    One chunk of ten pages: the next pages of `spec` that have no current OCR text. Idempotent and resumable (see the module
    doc). Returns counts only. Raises when the engine fails, so the queue retries it with backoff.
    """
    content = FileContent.objects.filter(pk=payload["content_id"]).first()
    if content is None:
        return {"skipped": "content_gone"}
    lang, user_id = payload["lang"], payload["user_id"]
    me = core_jobs.current_job()
    wait = _must_wait(content.id, user_id, me)
    if wait:
        _defer(payload, wait, me)
        return {"deferred": wait}
    since = _parse_since(payload.get("since"))
    remaining = _remaining(content, payload, since)
    if not remaining:
        return {"pages": 0, **_settle(content.id, lang, since)}
    batch = remaining[:CHUNK]
    attachment = _source_attachment(content, payload.get("document_id"))
    if attachment is None:
        raise objects.SourceMissing("No clean file to read.")
    FileContent.objects.filter(pk=content.pk, ocr_status__in=["pending", "partial"]).update(ocr_status="running")
    stored = _ocr_batch(content, attachment, batch, lang)
    search_index.refresh_pages(content.id, batch)
    state = _settle(content.id, lang, since)
    left = remaining[CHUNK:]
    if left:
        key = f"{JOB_OCR}:{content.id}:{payload.get('chain', 'x')}:{left[0]}"
        core_jobs.enqueue(
            JOB_OCR,
            {**payload, "pages": [left[0], left[min(CHUNK, len(left)) - 1]]},
            dedupe_key=key,
            priority=LATER_CHUNK_PRIORITY,
        )
    return {"pages": len(batch), "stored": stored, "left": len(left), **state}


def _remaining(content: FileContent, payload: dict, since: datetime | None) -> list[int]:
    valid = _ocr_pages_valid(content.id, since=since, lang=payload["lang"], engine=content.ocr_engine)
    protected = _protected_pages(content.id)
    return [p for p in pages_of_spec(payload.get("spec")) if p not in valid and p not in protected]


def _ocr_batch(content: FileContent, attachment, batch: list[int], lang: str) -> int:
    from ..worker import (
        ocr as engine,  # lazy: pulls in PDFium and Tesseract bindings, which the web process never needs
    )
    from ..worker.extract import normalise_text

    stored = engine_failures = 0
    with tempfile.TemporaryDirectory(prefix="ocr-src-") as tmp:
        source = os.path.join(tmp, "source.pdf")
        objects.download_to(source, attachment, limit=content.bytes)
        for number in batch:
            result = engine.ocr_pages(source, [number], lang)[0]
            if result.error and result.error not in PAGE_ERRORS:
                engine_failures += 1  # the page is left for the retry
            else:
                text = "" if result.error else normalise_text(result.text)
                conf = None if (result.error or not text) else min(100, max(0, int(round(result.conf))))
                words = None if result.error or not text else [list(w) for w in result.words]
                stored += file_pages.upsert_pages(content.id, [file_pages.PageWrite(number, text, "ocr", conf, words)])
            core_jobs.heartbeat()
    if engine_failures:
        raise RuntimeError(f"The OCR engine failed on {engine_failures} page(s).")
    return stored


def _settle(content_id, lang: str, since: datetime | None) -> dict:
    """
    Writes the progress the rows prove: `ocr_pages_done` (monotonic), `ocr_avg_conf` (the mean of the page scores, recomputed
    so a replayed chunk cannot skew a running mean) and the status: `partial` while pages are missing, `done` when every
    page promised to any request is read. Announces `searchable` for every document of the bytes once, on the way to done.
    """
    with transaction.atomic():
        content = FileContent.objects.select_for_update().get(pk=content_id)
        rows = FilePage.objects.filter(content_id=content_id, text_source="ocr")
        if since is not None:
            rows = rows.filter(updated_at__gte=since)
        scores = list(rows.exclude(ocr_conf__isnull=True).values_list("ocr_conf", flat=True))
        done = rows.count()
        total = max(content.ocr_pages_total, done)
        finished = done >= total and not _queued_pages_beyond(content, since, lang)
        was_done = content.ocr_status == "done"
        FileContent.objects.filter(pk=content_id).update(
            ocr_pages_done=Greatest(F("ocr_pages_done"), Value(done)),
            ocr_pages_total=total,
            ocr_avg_conf=round(sum(scores) / len(scores)) if scores else None,
            ocr_status="done" if finished else "partial",
            updated_at=timezone.now(),
        )
    if finished and not was_done:
        _announce_all(content_id)  # after the transaction, so a consumer reads the committed rows
    return {"status": "done" if finished else "partial", "done": done, "total": total}


def _queued_pages_beyond(content: FileContent, since, lang: str) -> bool:
    """True when another job of this content still has pages to read (so this chunk must not call the file done)."""
    valid = _ocr_pages_valid(content.id, since=since, lang=lang, engine=content.ocr_engine)
    protected = _protected_pages(content.id)
    return any(p not in valid and p not in protected for p in _queued_pages(content.id))


def _announce_all(content_id) -> None:
    for document in Document.objects.filter(content_id=content_id, deleted_at__isnull=True, status="ready"):
        _announce(document)


def give_up(payload: dict) -> dict:
    """
    The job ran out of attempts: the content is `failed` (unless it finished meanwhile) and the pages this request paid for and
    never got are refunded to the student, once (the job that calls this is the last of its chain).
    """
    content = FileContent.objects.filter(pk=payload["content_id"]).first()
    if content is None:
        return {"refunded": 0}
    since = _parse_since(payload.get("since"))
    unspent = len(_remaining(content, payload, since))
    refund = min(unspent, int(payload.get("charged", 0)))
    if refund:
        quota.refund_monthly(payload["user_id"], "ocr_pages", refund)
    FileContent.objects.filter(pk=content.pk).exclude(ocr_status="done").update(
        ocr_status="failed", updated_at=timezone.now()
    )
    return {"refunded": refund}
