"""The OCR chunk job end to end: real Tesseract on a generated scan, then the pipeline's rules with a fast stand-in engine."""
# ruff: noqa: F811 - pytest fixtures imported from `ocr_export_support` are redefined as test arguments

import shutil
from datetime import timedelta

import pytest
from django.contrib.postgres.search import SearchQuery
from django.utils import timezone

from core import events as bus
from core import jobs
from core.models import Job
from modules.coverage.tests.conftest import OTHER, USER
from modules.notes import events
from modules.notes.models import FileContent, FilePage
from modules.notes.services import ocr
from modules.notes.worker import ocr as engine

from .ocr_export_support import fake_storage, make_pdf_document, run_jobs, scanned_document  # noqa: F401
from .test_ocr_request import URL, used

pytestmark = pytest.mark.django_db
TYPES = ["notes.ocr"]
real_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract is not installed")


@pytest.fixture
def ready_events():
    seen = []
    listener = lambda **payload: seen.append(payload)  # noqa: E731
    bus.subscribe(events.NOTES_DOCUMENT_READY, listener)
    yield seen
    bus._subscribers[events.NOTES_DOCUMENT_READY].remove(listener)


def fake_engine(monkeypatch, *, fail_after=None, calls=None):
    """A stand-in for `worker.ocr.ocr_pages`: instant, deterministic, optionally dying after N pages (a killed worker)."""
    seen: list[int] = calls if calls is not None else []

    def fake(path, pages, lang="eng", **kwargs):
        out = []
        for n in pages:
            if fail_after is not None and len(seen) >= fail_after:
                raise RuntimeError("worker killed")
            seen.append(n)
            out.append(engine.OcrPage(n, f"credit page {n}", 88.0, ((0.1, 0.1, 0.2, 0.05, f"credit{n}"),)))
        return out

    monkeypatch.setattr(engine, "ocr_pages", fake)
    return seen


@real_tesseract
def test_a_scan_is_read_by_tesseract_searchable_and_the_boxes_sit_in_the_normalised_frame(
    api,
    fake_storage,
    tmp_path,
    ready_events,
):
    doc = scanned_document(fake_storage, USER, tmp_path, pages=2)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    assert run_jobs(TYPES) == 1  # two pages fit in one chunk
    content = FileContent.objects.get(pk=doc.content_id)
    assert (content.ocr_status, content.ocr_pages_done, content.ocr_pages_total) == ("done", 2, 2)
    assert content.ocr_avg_conf and content.ocr_avg_conf >= 60
    pages = {p.page: p for p in FilePage.objects.filter(content=content)}
    assert set(pages) == {1, 2} and all(p.text_source == "ocr" for p in pages.values())
    first = pages[1]
    assert "TAX" in first.text.upper() and "CREDIT" in first.text.upper() and first.ocr_conf >= 60
    assert first.words_schema == 1 and first.lang == "en"
    boxes = {w[4].upper(): w for w in first.words}
    x, y, w, h, _ = boxes["INPUT"]
    assert 0.05 < x < 0.2 and 0.08 < y < 0.16 and 0 < w < 0.4 and 0 < h < 0.1  # where the text was drawn, as fractions
    assert all(0 <= v <= 1 for word in first.words for v in word[:4]) and all(
        len(str(v)) <= 8 for word in first.words for v in word[:4]
    )
    assert FilePage.objects.filter(content=content, tsv=SearchQuery("credit", config="english")).count() == 2
    assert [e["stage"] for e in ready_events] == ["searchable"] and ready_events[0]["document_id"] == str(doc.id)
    assert ready_events[0]["pages"] == 2 and ready_events[0]["scanned"] is True


def test_a_long_scan_runs_in_chunks_of_ten_and_chains_the_next_chunk(
    api, fake_storage, tmp_path, monkeypatch, ready_events
):
    seen = fake_engine(monkeypatch)
    doc = scanned_document(fake_storage, USER, tmp_path, pages=25)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    first = Job.objects.get()
    assert run_jobs(TYPES, limit=1) == 1
    content = FileContent.objects.get(pk=doc.content_id)
    assert (content.ocr_status, content.ocr_pages_done) == ("partial", 10)  # searchable while it goes on
    assert seen == list(range(1, 11))
    nxt = Job.objects.exclude(pk=first.pk).get()
    assert nxt.priority < first.priority and nxt.dedupe_key == f"notes.ocr:{content.id}:{first.payload['chain']}:11"
    assert nxt.payload["pages"] == [11, 20] and nxt.status == "queued"
    assert ready_events == []  # not announced until the last page
    assert run_jobs(TYPES) == 2
    content.refresh_from_db()
    assert (content.ocr_status, content.ocr_pages_done) == ("done", 25) and seen == list(range(1, 26))
    assert len(ready_events) == 1
    assert [s for s in Job.objects.values_list("status", flat=True)] == ["done"] * 3


def test_a_worker_killed_at_page_n_resumes_at_page_n_plus_one(api, fake_storage, tmp_path, monkeypatch):
    doc = scanned_document(fake_storage, USER, tmp_path, pages=10)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    seen = fake_engine(monkeypatch, fail_after=7)
    assert run_jobs(TYPES, limit=1) == 1
    job = Job.objects.get()
    assert job.status == "queued" and job.attempts == 1  # the failure was recorded and the job goes back with a backoff
    assert sorted(FilePage.objects.filter(content=doc.content).values_list("page", flat=True)) == list(range(1, 8))
    assert FileContent.objects.get(pk=doc.content_id).ocr_pages_done in (0, 7)
    # a new process: only the database remembers
    resumed = fake_engine(monkeypatch)
    Job.objects.filter(pk=job.pk).update(run_after=timezone.now())
    run_jobs(TYPES)
    assert resumed == [8, 9, 10] and seen == list(range(1, 8))
    content = FileContent.objects.get(pk=doc.content_id)
    assert (content.ocr_status, content.ocr_pages_done) == ("done", 10)


def test_a_rerun_with_the_same_engine_is_a_no_op_and_native_text_is_never_overwritten(
    api, fake_storage, tmp_path, monkeypatch
):
    doc = scanned_document(fake_storage, USER, tmp_path, pages=4)
    FilePage.objects.create(content=doc.content, page=2, text="Native text of the page that is long enough")
    seen = fake_engine(monkeypatch)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    run_jobs(TYPES)
    assert seen == [1, 3, 4]
    native = FilePage.objects.get(content=doc.content, page=2)
    assert native.text_source == "native" and native.text.startswith("Native text")
    before = {p.page: p.updated_at for p in FilePage.objects.filter(content=doc.content)}
    # the same job again (a duplicate delivery): nothing is read, nothing is written
    job = Job.objects.get()
    jobs.enqueue("notes.ocr", job.payload, dedupe_key="notes.ocr:replay")
    run_jobs(TYPES)
    assert seen == [1, 3, 4]
    assert {p.page: p.updated_at for p in FilePage.objects.filter(content=doc.content)} == before


def test_ai_text_is_never_downgraded_to_ocr(api, fake_storage, tmp_path, monkeypatch):
    doc = scanned_document(fake_storage, USER, tmp_path, pages=2)
    FilePage.objects.create(content=doc.content, page=1, text="x", text_source="ai")
    seen = fake_engine(monkeypatch)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    run_jobs(TYPES)
    assert seen == [2] and FilePage.objects.get(content=doc.content, page=1).text_source == "ai"


def test_two_students_with_the_same_file_read_it_once(api, other_api, fake_storage, tmp_path, monkeypatch):
    seen = fake_engine(monkeypatch)
    mine = scanned_document(fake_storage, USER, tmp_path, pages=3)
    api.post(URL.format(mine.id), {"mode": "tesseract"})
    run_jobs(TYPES)
    twin_file = tmp_path / "twin.pdf"
    twin_file.write_bytes(fake_storage.objects[(mine.attachment.bucket, mine.attachment.path)])
    theirs = make_pdf_document(fake_storage, OTHER, twin_file, content=mine.content)
    res = other_api.post(URL.format(theirs.id), {"mode": "tesseract"})
    assert res.json_body["status"] == "done" and res.json_body["charged_pages"] == 0
    assert seen == [1, 2, 3] and used(OTHER) == 0 and used(USER) == 3
    assert (
        FilePage.objects.filter(content=theirs.content, text_source="ocr").count() == 3
    )  # their document sees the rows


def test_the_second_request_for_a_running_file_waits_instead_of_racing(api, fake_storage, tmp_path, monkeypatch):
    seen = fake_engine(monkeypatch)
    doc = scanned_document(fake_storage, USER, tmp_path, pages=4)
    api.post(URL.format(doc.id), {"mode": "tesseract", "pages": "1-2"})
    api.post(URL.format(doc.id), {"mode": "tesseract", "pages": "3-4"})
    first = jobs.claim_next(types=TYPES, worker="w1")  # running, not finished
    second = jobs.claim_next(types=TYPES, worker="w2")
    jobs.run_job(second)
    assert seen == []  # it stepped aside
    waiting = Job.objects.filter(status="queued")
    assert waiting.count() == 1 and waiting.get().run_after > timezone.now()
    assert waiting.get().payload["spec"] == second.payload["spec"]
    jobs.run_job(first)
    assert seen == [1, 2]


def test_one_ocr_document_per_student_at_a_time(api, fake_storage, tmp_path, monkeypatch):
    seen = fake_engine(monkeypatch)
    one = scanned_document(fake_storage, USER, tmp_path, pages=2)
    two = scanned_document(fake_storage, USER, tmp_path, pages=2, lines=("OTHER FILE", "SECOND"))
    api.post(URL.format(one.id), {"mode": "tesseract"})
    api.post(URL.format(two.id), {"mode": "tesseract"})
    running = jobs.claim_next(types=TYPES, worker="w1")
    blocked = jobs.claim_next(types=TYPES, worker="w2")
    jobs.run_job(blocked)
    assert seen == [] and Job.objects.filter(status="queued").count() == 1
    later = Job.objects.get(status="queued")
    assert later.run_after > timezone.now() and later.run_after < timezone.now() + timedelta(
        seconds=ocr.WAIT_STUDENT_SECONDS + 5
    )
    jobs.run_job(running)
    assert seen == [1, 2]
    Job.objects.filter(pk=later.pk).update(run_after=timezone.now())
    run_jobs(TYPES)
    assert seen == [1, 2, 1, 2] and all(
        FileContent.objects.get(pk=d.content_id).ocr_status == "done" for d in (one, two)
    )


def test_another_student_is_not_blocked_by_mine(api, other_api, fake_storage, tmp_path, monkeypatch):
    seen = fake_engine(monkeypatch)
    mine = scanned_document(fake_storage, USER, tmp_path, pages=2)
    theirs = scanned_document(fake_storage, OTHER, tmp_path, pages=2, lines=("THEIRS", "ONLY"))
    api.post(URL.format(mine.id), {"mode": "tesseract"})
    other_api.post(URL.format(theirs.id), {"mode": "tesseract"})
    running = jobs.claim_next(types=TYPES, worker="w1")
    other = jobs.claim_next(types=TYPES, worker="w2")
    jobs.run_job(other)
    assert seen == [1, 2] and not Job.objects.filter(status="queued").exists()
    jobs.run_job(running)


def test_a_job_that_runs_out_of_attempts_fails_the_content_and_refunds_the_unspent_pages(
    api, fake_storage, tmp_path, monkeypatch
):
    doc = scanned_document(fake_storage, USER, tmp_path, pages=6)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    assert used() == 6
    seen = fake_engine(monkeypatch, fail_after=2)  # two pages are read, then the engine dies for good
    for _ in range(5):
        Job.objects.filter(status="queued").update(run_after=timezone.now())
        run_jobs(TYPES, limit=1)
    job = Job.objects.get()
    assert job.status == "failed" and job.attempts == job.max_attempts
    content = FileContent.objects.get(pk=doc.content_id)
    assert content.ocr_status == "failed"
    assert FilePage.objects.filter(content=content).count() == 2
    assert used() == 2  # the four pages never read are given back
    assert seen == [1, 2]
    # asking again after a failure starts over for the missing pages only
    fake_engine(monkeypatch)
    again = api.post(URL.format(doc.id), {"mode": "tesseract"})
    assert again.json_body["charged_pages"] == 4 and used() == 6


def test_a_worker_that_goes_silent_on_the_last_attempt_still_fails_the_content_and_refunds(
    api, fake_storage, tmp_path, monkeypatch
):
    """The queue closes such a job itself (the handler never sees its last attempt), so it tells the OCR service."""
    doc = scanned_document(fake_storage, USER, tmp_path, pages=6)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    assert used() == 6
    Job.objects.filter(status="queued").update(max_attempts=1)
    assert jobs.claim_next(types=TYPES) is not None  # a worker takes it and goes silent before reading a page
    later = timezone.now() + jobs.VISIBILITY_TIMEOUT + timedelta(seconds=1)
    assert jobs.claim_next(types=TYPES, now=later) is None
    assert Job.objects.get(type="notes.ocr").status == "failed"
    assert FileContent.objects.get(pk=doc.content_id).ocr_status == "failed"
    assert used() == 0  # nothing was read, so everything is given back


def test_a_page_the_engine_cannot_render_is_stored_empty_so_the_chain_moves_on(
    api, fake_storage, tmp_path, monkeypatch
):
    def fake(path, pages, lang="eng", **kwargs):
        return [
            engine.OcrPage(n, "", 0.0, (), "render_failed") if n == 2 else engine.OcrPage(n, f"text {n}", 90.0, ())
            for n in pages
        ]

    monkeypatch.setattr(engine, "ocr_pages", fake)
    doc = scanned_document(fake_storage, USER, tmp_path, pages=3)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    run_jobs(TYPES)
    content = FileContent.objects.get(pk=doc.content_id)
    assert content.ocr_status == "done" and content.ocr_pages_done == 3
    empty = FilePage.objects.get(content=content, page=2)
    assert empty.text == "" and empty.ocr_conf is None and empty.words is None and empty.text_source == "ocr"
    assert content.ocr_avg_conf == 90


def test_progress_only_grows_and_the_average_is_recomputed_not_accumulated(api, fake_storage, tmp_path, monkeypatch):
    doc = scanned_document(fake_storage, USER, tmp_path, pages=2)
    fake_engine(monkeypatch)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    run_jobs(TYPES)
    ocr._settle(doc.content_id, "eng", None)
    ocr._settle(doc.content_id, "eng", None)  # a replayed chunk settles to the same numbers
    content = FileContent.objects.get(pk=doc.content_id)
    assert (content.ocr_pages_done, content.ocr_avg_conf, content.ocr_status) == (2, 88, "done")
    FileContent.objects.filter(pk=content.pk).update(ocr_pages_done=9)
    ocr._settle(doc.content_id, "eng", None)
    assert FileContent.objects.get(pk=content.pk).ocr_pages_done == 9  # greatest(): never moves backwards


def test_a_document_whose_file_is_gone_fails_the_attempt_not_the_worker(api, fake_storage, tmp_path, monkeypatch):
    doc = scanned_document(fake_storage, USER, tmp_path, pages=2)
    fake_engine(monkeypatch)
    api.post(URL.format(doc.id), {"mode": "tesseract"})
    fake_storage.objects.clear()
    run_jobs(TYPES, limit=1)
    job = Job.objects.get()
    assert job.status == "queued" and "Storage" in job.last_error or "empty" in job.last_error
