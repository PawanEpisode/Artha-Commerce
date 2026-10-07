"""`reextract_content`: failed text is retried, OCR text survives, dry runs change nothing."""

import pytest
from django.core.management import call_command

from core.models import Job
from modules.notes.models import FileContent, FilePage

from .factories import ALICE, make_content, make_document

pytestmark = pytest.mark.django_db


def held(**fields):
    content = make_content(page_count=3, **fields)
    return content, make_document(ALICE, content=content)


def test_failed_content_is_queued_again_and_other_content_is_left_alone():
    failed, _ = held(text_status="failed", text_pages_done=2)
    fine, _ = held(text_status="done", text_pages_done=3)
    locked, _ = held(text_status="locked")
    orphan = make_content(page_count=3, text_status="failed")
    call_command("reextract_content")
    job = Job.objects.get(type="notes.extract_text")
    assert job.payload["content_id"] == str(failed.pk) and job.dedupe_key == f"notes.extract_text:{failed.pk}"
    assert (
        FileContent.objects.get(pk=failed.pk).text_status == "pending"
        and FileContent.objects.get(pk=failed.pk).text_pages_done == 0
    )
    assert (
        FileContent.objects.get(pk=fine.pk).text_status == "done"
        and FileContent.objects.get(pk=locked.pk).text_status == "locked"
    )
    assert FileContent.objects.get(pk=orphan.pk).text_status == "failed"  # nobody holds it


def test_all_and_by_id_and_dry_run():
    one, _ = held(text_status="done", text_pages_done=3)
    two, _ = held(text_status="done", text_pages_done=3)
    call_command("reextract_content", "--all", "--dry-run")
    assert not Job.objects.exists() and FileContent.objects.get(pk=one.pk).text_status == "done"
    call_command("reextract_content", "--content", str(one.pk))
    assert [j.payload["content_id"] for j in Job.objects.all()] == [str(one.pk)]
    call_command("reextract_content", "--all")
    assert Job.objects.count() == 2 and FileContent.objects.get(pk=two.pk).text_status == "pending"


def test_queueing_again_deletes_no_stored_page():
    content, _ = held(text_status="failed")
    FilePage.objects.create(content=content, page=1, text="ocr words", text_source="ocr", ocr_conf=90)
    call_command("reextract_content")
    assert FilePage.objects.get(content=content, page=1).text == "ocr words"
