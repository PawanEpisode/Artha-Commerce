"""Unlock for search: the password is sealed, used once in the worker, and gone; the text stays private to the student."""
# ruff: noqa: F811 - pytest fixtures imported from the support modules are redefined as test arguments

import json
import uuid
from datetime import timedelta

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone

from core import jobs as core_jobs
from core.models import Job
from modules.coverage.tests.conftest import OTHER, USER
from modules.notes.models import Document, FileContent, FilePage
from modules.notes.services import unlock

from .ai_support import ai_on  # noqa: F401
from .ocr_export_support import fake_storage, make_pdf_document  # noqa: F401
from .worker.fixtures import make_pdfs as mk

pytestmark = pytest.mark.django_db
PASSWORD = "p@ss w0rd ✓"
URL = "/notes/documents/{}/unlock/"


@pytest.fixture
def keyed(settings):
    settings.NOTES_UNLOCK_FERNET_KEYS = Fernet.generate_key().decode()


def locked_document(fake, tmp_path, user=USER, *, password="secret", **allow):
    plain = mk.text_pdf(tmp_path / f"plain-{uuid.uuid4().hex[:5]}.pdf", pages=3)
    path = mk.encrypted_pdf(tmp_path / f"locked-{uuid.uuid4().hex[:5]}.pdf", plain, user=password, **allow)
    doc = make_pdf_document(fake, user, path, page_count=None, is_encrypted=True, text_status="locked")
    Document.objects.filter(pk=doc.pk).update(status="needs_password", page_count=None)
    doc.refresh_from_db()
    return doc


def run_worker():
    return core_jobs.run_pending(types=["notes.unlock"], worker="test")


def ask(api, doc, password="secret"):
    return api.post(URL.format(doc.id), {"password": password})


def test_it_is_closed_until_the_ai_flag_is_on_and_a_key_is_set(api, fake_storage, tmp_path, settings):
    doc = locked_document(fake_storage, tmp_path)
    assert ask(api, doc).status_code == 403  # flag unset: fails closed


def test_without_a_key_nothing_is_queued(api, ai_on, fake_storage, tmp_path, settings):
    settings.NOTES_UNLOCK_FERNET_KEYS = ""
    doc = locked_document(fake_storage, tmp_path)
    res = ask(api, doc)
    assert (res.status_code, res.json_body["error"]["code"]) == (503, "unlock_unavailable")
    assert not Job.objects.filter(type="notes.unlock").exists()


def test_the_password_is_sealed_in_the_queue_and_never_stored_in_clear(api, ai_on, keyed, fake_storage, tmp_path):
    doc = locked_document(fake_storage, tmp_path, password=PASSWORD)
    res = ask(api, doc, PASSWORD)
    assert res.status_code == 202 and res.json_body["unlock_status"] == "waiting"
    job = Job.objects.get(type="notes.unlock")
    assert PASSWORD not in json.dumps(job.payload) and job.payload["secret"]
    assert unlock.unseal(job.payload["secret"]) == PASSWORD
    assert PASSWORD not in json.dumps(res.json_body)


def test_the_right_password_makes_the_text_searchable_on_a_private_copy_and_clears_the_secret(
    api, ai_on, keyed, fake_storage, tmp_path
):
    doc = locked_document(fake_storage, tmp_path)
    shared = doc.content_id
    ask(api, doc)
    assert run_worker() == 1
    doc.refresh_from_db()
    assert (doc.status, doc.unlock_status, doc.page_count) == ("ready", "done", 3)
    content = FileContent.objects.get(pk=doc.content_id)
    assert content.pk != shared and content.sha256 == unlock.private_sha(doc.id) and content.text_status == "done"
    assert content.is_encrypted and content.text_pages_done == 3
    pages = {p.page: p.text for p in FilePage.objects.filter(content_id=content.pk)}
    assert "Input tax credit" in pages[1] and len(pages) == 3
    assert not FilePage.objects.filter(content_id=shared).exists()  # the shared locked row learned nothing
    job = Job.objects.get(type="notes.unlock")
    assert job.status == "done" and "secret" not in job.payload and "Input tax" not in json.dumps(job.result)
    assert FileContent.objects.get(pk=shared).orphaned_at is not None  # nobody else points at it


def test_someone_with_the_same_file_and_no_password_gets_no_text(api, ai_on, keyed, fake_storage, tmp_path):
    mine = locked_document(fake_storage, tmp_path)
    # the other student's document points at the SAME shared content row (identical bytes)
    theirs = Document.objects.create(
        user_id=OTHER,
        attachment=mine.attachment,
        content=mine.content,
        title="x",
        status="needs_password",
        bytes=mine.bytes,
    )
    ask(api, mine)
    run_worker()
    theirs.refresh_from_db()
    assert theirs.content_id == mine.content_id != Document.objects.get(pk=mine.pk).content_id
    assert theirs.status == "needs_password"
    assert not FilePage.objects.filter(content_id=theirs.content_id).exists()


def test_a_wrong_password_is_reported_and_counted(api, ai_on, keyed, fake_storage, tmp_path):
    doc = locked_document(fake_storage, tmp_path)
    ask(api, doc, "nope")
    run_worker()
    doc.refresh_from_db()
    assert (doc.status, doc.unlock_status, doc.unlock_reason, doc.unlock_failures) == (
        "needs_password",
        "failed",
        "wrong_password",
        1,
    )
    assert "secret" not in Job.objects.get(type="notes.unlock").payload
    again = ask(api, doc, "secret")  # the right one still works after a failure
    assert again.status_code == 202
    run_worker()
    doc.refresh_from_db()
    assert (doc.status, doc.unlock_status, doc.unlock_failures) == ("ready", "done", 0)


def test_five_wrong_passwords_in_an_hour_lock_the_try_until_it_passes(api, ai_on, keyed, fake_storage, tmp_path):
    doc = locked_document(fake_storage, tmp_path)
    for _ in range(unlock.MAX_FAILURES):
        assert ask(api, doc, "nope").status_code == 202
        run_worker()
    res = ask(api, doc, "secret")
    assert (res.status_code, res.json_body["error"]["code"]) == (429, "too_many_attempts")
    Document.objects.filter(pk=doc.pk).update(unlock_failed_at=timezone.now() - timedelta(hours=2))
    assert ask(api, doc, "secret").status_code == 202


def test_a_pdf_that_forbids_copying_text_is_refused_even_with_its_password(api, ai_on, keyed, fake_storage, tmp_path):
    doc = locked_document(fake_storage, tmp_path, extract=False)
    ask(api, doc)
    run_worker()
    doc.refresh_from_db()
    assert (doc.unlock_status, doc.unlock_reason, doc.status) == ("failed", "restricted", "needs_password")
    assert not FilePage.objects.exists()


def test_a_second_try_while_one_is_running_and_a_document_that_is_not_locked_are_conflicts(
    api, ai_on, keyed, fake_storage, tmp_path
):
    doc = locked_document(fake_storage, tmp_path)
    assert ask(api, doc).status_code == 202
    busy = ask(api, doc)
    assert (busy.status_code, busy.json_body["error"]["code"]) == (409, "unlock_in_progress")
    Document.objects.filter(pk=doc.pk).update(status="ready", unlock_status="none")
    gone = ask(api, doc)
    assert (gone.status_code, gone.json_body["error"]["code"]) == (409, "not_locked")


def test_another_students_document_is_not_found(api, ai_on, keyed, fake_storage, tmp_path):
    doc = locked_document(fake_storage, tmp_path, user=OTHER)
    assert ask(api, doc).status_code == 404


def test_a_token_that_outlived_its_hour_is_cleared_and_the_try_fails_as_expired(
    api, ai_on, keyed, fake_storage, tmp_path
):
    doc = locked_document(fake_storage, tmp_path)
    ask(api, doc)
    Job.objects.filter(type="notes.unlock").update(
        created_at=timezone.now() - timedelta(hours=2), run_after=timezone.now() + timedelta(days=1)
    )
    assert unlock.expire_secrets() == 1
    assert "secret" not in Job.objects.get(type="notes.unlock").payload
    doc.refresh_from_db()
    assert (doc.unlock_status, doc.unlock_reason) == ("failed", "expired")


def test_garbage_is_not_a_token(keyed):
    assert unlock.unseal("not-a-token") is None
    assert unlock.unseal("") is None


def test_the_password_never_reaches_sentry():
    from core.sentry import before_send

    event = {"request": {"url": "https://api.example.com/api/v1/notes/documents/x/unlock/", "data": {"password": "pw"}}}
    out = before_send(event)
    assert "data" not in out["request"]
    event = {"request": {"url": "https://api.example.com/api/v1/other/", "data": {"password": "pw", "secret": "s"}}}
    assert before_send(event)["request"]["data"] == {"password": "[Filtered]", "secret": "[Filtered]"}
