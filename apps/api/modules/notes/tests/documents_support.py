"""Shared builders for the document, pipeline and PDF search tests: a fake object store and the upload flow driven over HTTP."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from django.db import connection

from core import events as bus
from core import feature_flags, jobs
from modules.media.models import Attachment
from modules.media.tests.conftest import FakeStorage
from modules.notes import jobs as notes_jobs
from modules.notes.models import Document

from .worker.fixtures import make_pdfs as mk

MB = 1024 * 1024
HEAVY = list(notes_jobs.HEAVY_TYPES)


@pytest.fixture
def fake_storage(monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr("modules.media.services.get_storage", lambda: fake)
    return fake


@pytest.fixture
def pdf_flag_off(settings, monkeypatch):
    class Off:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return False if key == "notes_pdf" else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Off())
    feature_flags.clear_flag_cache()
    yield
    feature_flags.clear_flag_cache()


@pytest.fixture
def capture_events():
    """`seen = capture_events("name")` records the payloads of a domain event and unsubscribes only itself afterwards."""
    added = []

    def capture(name):
        seen: list[dict] = []

        def record(**payload):
            seen.append(payload)

        bus.subscribe(name, record)
        added.append((name, record))
        return seen

    yield capture
    for name, record in added:
        bus._subscribers[name].remove(record)


def body(size=1000, **extra) -> dict:
    return {
        "client_id": str(uuid.uuid4()),
        "filename": "GST notes.pdf",
        "bytes": size,
        "mime": "application/pdf",
        **extra,
    }


def reserve(api, size=1000, **extra):
    return api.post("/notes/documents/", body(size, **extra))


def put_bytes(fake: FakeStorage, document_id, data: bytes) -> Attachment:
    """What the browser does after `POST documents/`: PUT the file to the signed URL (here: straight into the fake store)."""
    attachment = Document.objects.get(pk=document_id).attachment
    fake.upload(attachment.bucket, attachment.path, data, content_type="application/pdf", cache_control="")
    return attachment


def upload_and_complete(api, fake, data: bytes, capture, **extra) -> dict:
    """Reserve, PUT, complete (running the after-commit hooks) and return the Document body."""
    res = reserve(api, len(data), **extra)
    assert res.status_code == 201, res.json_body
    doc_id = res.json_body["document"]["id"]
    put_bytes(fake, doc_id, data)
    with capture(execute=True):
        done = api.post(f"/notes/documents/{doc_id}/complete/")
    assert done.status_code == 200, done.json_body
    return done.json_body


def run_worker(max_jobs: int = 50) -> int:
    return jobs.run_pending(types=HEAVY, max_jobs=max_jobs, worker="test-worker")


def make_pdf(tmp_path: Path, kind: str = "text", pages: int = 3, name: str | None = None) -> bytes:
    path = tmp_path / (name or f"{kind}-{uuid.uuid4().hex[:6]}.pdf")
    if kind == "text":
        mk.text_pdf(path, pages)
    elif kind == "scanned":
        mk.scanned_pdf(path, pages)
    elif kind == "encrypted":
        src = mk.text_pdf(tmp_path / f"src-{uuid.uuid4().hex[:6]}.pdf", pages)
        mk.encrypted_pdf(path, src)
    elif kind == "corrupt":
        src = mk.text_pdf(tmp_path / f"src-{uuid.uuid4().hex[:6]}.pdf", pages)
        mk.truncated_pdf(path, src)
    elif kind == "notpdf":
        path.write_bytes(b"MZ\x90\x00 not a pdf at all " * 50)
    else:
        raise ValueError(kind)
    return path.read_bytes()


def on_postgres() -> bool:
    return connection.vendor == "postgresql"
