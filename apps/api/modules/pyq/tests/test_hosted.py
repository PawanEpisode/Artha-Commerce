"""Hosted past-paper PDFs: publishing them to the private bucket, and opening one in the reader."""

from __future__ import annotations

import uuid

import pytest

from core import feature_flags
from modules.media.models import Attachment
from modules.notes.models import Document
from modules.pyq import hosted
from modules.pyq.domain.sources import SourceFile
from modules.pyq.models import PaperLink, PyqPaper

pytestmark = pytest.mark.django_db


class FakeStore:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload(self, bucket, path, data, *, content_type, cache_control):
        self.objects[(bucket, path)] = data

    def delete(self, bucket, paths):
        for path in paths:
            self.objects.pop((bucket, path), None)


@pytest.fixture
def paper(syllabus_tree):
    level = syllabus_tree.level
    subject = syllabus_tree.subjects.first()
    return PyqPaper.objects.create(
        course=level.course,
        level=level,
        subject_key=subject.key,
        subject=subject,
        term_code="2024-06",
        external_ref="pyq:cma-final:p13:2024-06",
        title="CMA Final June 2024: Corporate and Economic Laws (Paper 13)",
        total_marks=100,
        status=PyqPaper.Status.PUBLISHED,
    )


def _source(tmp_path, kind="paper", body=b"%PDF-1.7 a paper") -> SourceFile:
    path = tmp_path / f"{kind}.pdf"
    path.write_bytes(body)
    return SourceFile(path, "13", "2024-06", kind, "Question Paper (PDF)")


def test_publishing_hosts_the_pdf_privately_and_links_it(paper, tmp_path):
    store = FakeStore()

    outcome = hosted.publish_pdf(paper, _source(tmp_path), store=store)

    assert outcome == "published"
    link = paper.links.get()
    attachment = Attachment.objects.get(id=link.attachment_id)
    assert (link.url, link.verified, link.link_status) == ("", True, "ok")
    assert attachment.user_id == hosted.PLATFORM_OWNER_ID and attachment.status == "clean"
    assert attachment.mime == "application/pdf" and attachment.bytes == len(b"%PDF-1.7 a paper")
    assert str(link.attachment_id) in attachment.path and ".pdf" in attachment.path and "paper" not in attachment.path
    assert store.objects[(attachment.bucket, attachment.path)] == b"%PDF-1.7 a paper"
    paper.refresh_from_db()
    assert paper.delivery == PyqPaper.Delivery.HOSTED
    assert paper.rights_basis == PyqPaper.RightsBasis.INSTITUTE_MATERIAL


def test_running_again_keeps_what_is_hosted_and_force_replaces_it(paper, tmp_path):
    store = FakeStore()
    hosted.publish_pdf(paper, _source(tmp_path), store=store)
    first = paper.links.get().attachment_id

    assert hosted.publish_pdf(paper, _source(tmp_path), store=store) == "kept"
    assert paper.links.get().attachment_id == first

    assert hosted.publish_pdf(paper, _source(tmp_path, body=b"%PDF-1.7 newer"), force=True, store=store) == "replaced"
    link = paper.links.get()
    assert link.attachment_id != first
    assert Attachment.objects.get(id=first).status == Attachment.Status.DELETING  # the old object goes with its job


def test_a_file_that_is_not_a_pdf_is_refused_and_nothing_is_left(paper, tmp_path):
    store = FakeStore()

    with pytest.raises(hosted.PdfRejected):
        hosted.publish_pdf(paper, _source(tmp_path, body=b"<html>not a pdf</html>"), store=store)

    assert store.objects == {} and not paper.links.exists() and not Attachment.objects.exists()


def test_a_failed_database_write_removes_the_uploaded_object(paper, tmp_path, monkeypatch):
    store = FakeStore()
    monkeypatch.setattr(PaperLink.objects, "create", lambda **kw: (_ for _ in ()).throw(RuntimeError("db down")))

    with pytest.raises(RuntimeError):
        hosted.publish_pdf(paper, _source(tmp_path), store=store)

    assert store.objects == {} and not Attachment.objects.exists()


def _flags(monkeypatch, settings, on_keys):
    class Client_:
        def get_feature_flag(self, key, distinct_id, **kwargs):
            return True if key in on_keys else None

    settings.POSTHOG_API_KEY = "phc_test"
    monkeypatch.setattr(feature_flags, "_client", Client_())
    feature_flags.clear_flag_cache()


def test_opening_a_hosted_paper_adds_it_to_the_library_once(api, paper, tmp_path, monkeypatch, settings):
    hosted.publish_pdf(paper, _source(tmp_path), store=FakeStore())
    link = paper.links.get()
    _flags(monkeypatch, settings, {"question_bank", "pyq_bank", "notes", "notes_pdf"})

    first = api.post(f"/pyq/papers/{paper.id}/links/{link.id}/open/")
    again = api.post(f"/pyq/papers/{paper.id}/links/{link.id}/open/")

    assert first.status_code == 200 and again.status_code == 200
    assert first.json_body["document_id"] == again.json_body["document_id"]
    document = Document.objects.get(id=first.json_body["document_id"])
    assert (document.origin, document.bytes, document.attachment_id) == ("platform", 0, link.attachment_id)
    assert "Corporate and Economic Laws" in document.title


def test_opening_needs_the_pdf_reader_flag_and_a_hosted_link(api, paper, tmp_path, monkeypatch, settings):
    hosted.publish_pdf(paper, _source(tmp_path), store=FakeStore())
    link = paper.links.get()
    outside = PaperLink.objects.create(paper=paper, link_kind="other", url="https://icmai.in/x.pdf")

    assert api.post(f"/pyq/papers/{paper.id}/links/{link.id}/open/").status_code == 403  # notes_pdf is off

    _flags(monkeypatch, settings, {"question_bank", "pyq_bank", "notes", "notes_pdf"})
    assert api.post(f"/pyq/papers/{paper.id}/links/{outside.id}/open/").status_code == 404  # not a hosted file
    assert api.post(f"/pyq/papers/{paper.id}/links/{uuid.uuid4()}/open/").status_code == 404

    PyqPaper.objects.filter(id=paper.id).update(status=PyqPaper.Status.WITHDRAWN)
    assert api.post(f"/pyq/papers/{paper.id}/links/{link.id}/open/").status_code == 404  # a withdrawn paper is closed
