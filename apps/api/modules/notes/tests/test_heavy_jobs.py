"""The cron tick runs light jobs only; heavy ones (scan, inspect, text, OCR, export) wait for the worker."""

import pytest

from core import jobs
from core.models import Job
from modules.notes import jobs as notes_jobs

pytestmark = pytest.mark.django_db


def test_light_and_heavy_types_do_not_overlap_and_cover_the_r2_and_r3_work():
    assert not set(notes_jobs.LIGHT_TYPES) & set(notes_jobs.HEAVY_TYPES)
    assert set(notes_jobs.HEAVY_TYPES) == {
        "notes.inspect",
        "notes.extract_text",
        "notes.ocr",
        "notes.export_pdf",
        "notes.export_archive",
        "notes.summarize",
        "notes.ocr_ai",  # R3: waits on Google, so it runs in the worker, never in the tick
        "notes.reanchor",  # R3: opens two PDFs, so it runs in the worker
        "notes.unlock",  # R3: holds a password for a moment and reads a whole PDF, so the worker
        "media.scan",
    }
    assert notes_jobs.JOB_INSPECT == "notes.inspect"


def test_the_tick_leaves_heavy_jobs_queued_even_with_a_handler_registered(monkeypatch):
    ran = []
    for job_type in notes_jobs.HEAVY_TYPES:
        monkeypatch.setitem(jobs._handlers, job_type, lambda payload, t=job_type: ran.append(t))
        jobs.enqueue(job_type, {"document_id": "d"}, dedupe_key=f"{job_type}:d")
    result = notes_jobs.tick()
    assert ran == [] and result["ran"] >= 0
    heavy = Job.objects.filter(type__in=notes_jobs.HEAVY_TYPES)
    assert heavy.count() == len(notes_jobs.HEAVY_TYPES) and set(heavy.values_list("status", flat=True)) == {"queued"}
    assert all(j.attempts == 0 for j in heavy)


def test_the_worker_can_claim_what_the_tick_leaves():
    jobs.enqueue(notes_jobs.JOB_INSPECT, {"document_id": "d"})
    notes_jobs.tick()
    job = jobs.claim_next(types=notes_jobs.HEAVY_TYPES, worker="worker")
    assert job is not None and job.type == "notes.inspect" and job.attempts == 1
