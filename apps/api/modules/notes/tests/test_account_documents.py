"""Account export and erasure cover documents, marks, page ranges, exports, item tags and files, and only the student's own."""

import pytest

from core import jobs
from modules.media.models import Attachment
from modules.notes import selectors
from modules.notes.models import (
    Annotation,
    Document,
    DocumentChapter,
    ExportJob,
    FileContent,
    ItemTag,
    QuotaUsage,
)
from modules.notes.services import account, links, quota
from modules.syllabus.models import Chapter

from .factories import (
    ALICE,
    BOB,
    make_annotation,
    make_attachment,
    make_content,
    make_document,
    make_export,
    make_note,
    make_tag,
)

pytestmark = pytest.mark.django_db


def populate(user_id, content, scheme_chapter, tag_name="revise"):
    """A student with a document (file, cover, mark, range, export, tags), a note and quota in use."""
    cover = make_attachment(user_id, kind="note_image", mime="image/webp", ext="webp", bytes=50)
    doc = make_document(user_id, content=content, cover_attachment=cover, bytes=1000)
    mark = make_annotation(doc, comment="my private reading note", quote_exact="a quote")
    link = links.link_columns(scheme_chapter.id, None)
    DocumentChapter.objects.create(user_id=user_id, document=doc, page_from=1, page_to=5, **link)
    export_file = make_attachment(user_id, kind="note_export", mime="application/zip", ext="zip", bytes=10)
    export = make_export(doc, attachment=export_file, status="done")
    tag = make_tag(user_id, tag_name)
    ItemTag.objects.create(user_id=user_id, tag=tag, document=doc)
    ItemTag.objects.create(user_id=user_id, tag=tag, annotation=mark)
    note = make_note(user_id)
    ItemTag.objects.create(user_id=user_id, tag=tag, note=note)
    quota.reserve_document(user_id, 1000)
    return {"doc": doc, "mark": mark, "export": export, "files": {doc.attachment_id, cover.id, export_file.id}}


@pytest.fixture
def chapter(scheme):
    return Chapter.objects.get(key="gst-itc")


def test_erasing_a_student_removes_documents_and_everything_hanging_off_them(chapter):
    shared, only_alice = make_content(), make_content()
    mine = populate(ALICE, only_alice, chapter)
    theirs = populate(BOB, shared, chapter)
    populate(ALICE, shared, chapter, "again")  # Alice also holds the file Bob holds

    report = account.delete_all_for_user(ALICE)

    assert report["documents"] == 2 and report["marks"] == 2 and report["page_ranges"] == 2 and report["exports"] == 2
    assert report["files"] == 6 and report["notes"] == 2
    for model in (Document, Annotation, DocumentChapter, ExportJob, ItemTag):
        assert not model.objects.filter(user_id=ALICE).exists(), model.__name__
    assert not QuotaUsage.objects.filter(pk=ALICE).exists()
    # Bob's rows are untouched, down to the last field
    assert Document.objects.filter(user_id=BOB, pk=theirs["doc"].pk).count() == 1
    assert Annotation.objects.get(pk=theirs["mark"].pk).comment == "my private reading note"
    assert ExportJob.objects.filter(user_id=BOB).count() == 1 and ItemTag.objects.filter(user_id=BOB).count() == 3
    assert DocumentChapter.objects.filter(user_id=BOB).count() == 1
    assert QuotaUsage.objects.get(pk=BOB).docs_active == 1
    # derived content: orphaned only when nobody references it
    assert FileContent.objects.get(pk=only_alice.pk).orphaned_at is not None
    assert FileContent.objects.get(pk=shared.pk).orphaned_at is None
    assert report["contents_orphaned"] == 1
    # files are queued for deletion through media: stop being served now, objects leave with the worker
    queued = Attachment.objects.filter(pk__in=mine["files"])
    assert queued.count() == 3 and set(queued.values_list("status", flat=True)) == {"deleting"}
    assert {j.payload["attachment_id"] for j in jobs.Job.objects.filter(type="media.delete")} >= {
        str(i) for i in mine["files"]
    }
    assert not Attachment.objects.filter(user_id=BOB, status="deleting").exists()


def test_erasing_twice_is_harmless(chapter):
    populate(ALICE, make_content(), chapter)
    account.delete_all_for_user(ALICE)
    again = account.delete_all_for_user(ALICE)
    assert again["documents"] == 0 and again["marks"] == 0 and again["files"] == 0


def test_the_files_really_go_when_the_worker_runs_the_delete_jobs(chapter, monkeypatch):
    from modules.media import services as media

    removed = []

    class Store:
        def delete(self, bucket, paths):
            removed.extend(paths)

    monkeypatch.setattr(media, "get_storage", lambda: Store())
    mine = populate(ALICE, make_content(), chapter)
    account.delete_all_for_user(ALICE)
    while (job := jobs.claim_next(types=["media.delete"])) is not None:
        jobs.run_job(job)
    assert not Attachment.objects.filter(pk__in=mine["files"]).exists() and len(removed) == 3
    assert not QuotaUsage.objects.filter(pk=ALICE).exists()  # releasing a gone student's quota is tolerated


def test_the_export_carries_documents_marks_ranges_exports_and_their_tags_for_this_student_only(chapter):
    content = make_content()
    mine = populate(ALICE, content, chapter)
    populate(BOB, make_content(), chapter)

    data = selectors.export_all(ALICE)

    (doc,) = data["documents"]
    assert doc["id"] == str(mine["doc"].id) and doc["tags"] == ["revise"] and doc["status"] == "ready"
    (mark,) = data["marks"]
    assert (
        mark["id"] == str(mine["mark"].id)
        and mark["comment"] == "my private reading note"
        and mark["tags"] == ["revise"]
    )
    assert [r["page_to"] for r in data["page_ranges"]] == [5]
    assert [e["id"] for e in data["exports"]] == [str(mine["export"].id)]
    assert len(data["notes"]) == 1 and data["notes"][0]["tags"] == ["revise"]
    everything = str(data)
    for key in ("user_id", "search_tsv"):
        assert key not in {
            k
            for rows in (data["documents"], data["marks"], data["page_ranges"], data["exports"])
            for r in rows
            for k in r
        }, key
    assert str(BOB) not in everything


def test_the_export_is_empty_but_well_formed_for_a_student_without_documents():
    data = selectors.export_all(ALICE)
    assert data["documents"] == [] and data["marks"] == [] and data["page_ranges"] == [] and data["exports"] == []


def test_orphaning_skips_content_that_is_still_referenced_and_can_be_adopted_again(chapter):
    from modules.notes.services import content

    held, loose = make_content(), make_content()
    make_document(ALICE, content=held)
    assert content.mark_orphaned([held.pk, loose.pk, None]) == 1
    assert FileContent.objects.get(pk=held.pk).orphaned_at is None
    assert content.mark_orphaned([loose.pk]) == 0  # idempotent: already marked
    content.clear_orphaned(loose.pk)
    assert FileContent.objects.get(pk=loose.pk).orphaned_at is None
