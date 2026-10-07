"""
The database itself refuses cross-student links (composite foreign keys, migrations 0003 to 0005), overlapping page ranges
and a tag on two items. PostgreSQL only: SQLite keeps the service-level checks.
"""

import pytest
from django.db import IntegrityError, connection, transaction

from modules.notes.models import (
    Annotation,
    Document,
    DocumentChapter,
    ExportJob,
    ItemTag,
    NoteImage,
    NoteVersion,
    Tag,
)
from modules.syllabus.models import Chapter

from .factories import ALICE, BOB, make_annotation, make_attachment, make_document, make_note, make_tag

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(connection.vendor != "postgresql", reason="composite keys are PostgreSQL DDL"),
]


def refused(create):
    """True when the database raised an integrity error for `create()` (in a savepoint, so the test goes on)."""
    with pytest.raises(IntegrityError), transaction.atomic():
        create()


def test_a_tag_cannot_cross_students():
    note, tag = make_note(ALICE), make_tag(BOB)
    refused(lambda: ItemTag.objects.create(user_id=ALICE, tag=tag, note=note))


def test_a_note_tag_row_must_carry_the_notes_owner():
    note, tag = make_note(ALICE), make_tag(ALICE)
    refused(lambda: ItemTag.objects.create(user_id=BOB, tag=tag, note=note))
    assert ItemTag.objects.create(user_id=ALICE, tag=tag, note=note).pk


def test_an_annotation_tag_cannot_cross_students():
    doc = make_document(ALICE)
    mark = make_annotation(doc)
    refused(lambda: ItemTag.objects.create(user_id=BOB, tag=make_tag(BOB), annotation=mark))
    refused(lambda: ItemTag.objects.create(user_id=ALICE, tag=make_tag(BOB, "b2"), annotation=mark))
    assert ItemTag.objects.create(user_id=ALICE, tag=make_tag(ALICE), annotation=mark).pk


def test_a_document_tag_cannot_cross_students():
    doc = make_document(ALICE)
    refused(lambda: ItemTag.objects.create(user_id=BOB, tag=make_tag(BOB), document=doc))
    assert ItemTag.objects.create(user_id=ALICE, tag=make_tag(ALICE), document=doc).pk


def test_a_tag_row_names_exactly_one_target():
    note, tag, doc = make_note(ALICE), make_tag(ALICE), make_document(ALICE)
    refused(lambda: ItemTag.objects.create(user_id=ALICE, tag=tag))
    refused(lambda: ItemTag.objects.create(user_id=ALICE, tag=tag, note=note, document=doc))


def test_the_same_tag_cannot_sit_twice_on_one_item():
    doc, tag = make_document(ALICE), make_tag(ALICE)
    ItemTag.objects.create(user_id=ALICE, tag=tag, document=doc)
    refused(lambda: ItemTag.objects.create(user_id=ALICE, tag=tag, document=doc))


def test_a_note_image_cannot_point_at_another_students_note_or_file():
    note = make_note(ALICE)
    mine = make_attachment(ALICE, kind="note_image", mime="image/webp", ext="webp")
    theirs = make_attachment(BOB, kind="note_image", mime="image/webp", ext="webp")
    refused(lambda: NoteImage.objects.create(note=note, attachment=theirs, user_id=ALICE))
    refused(lambda: NoteImage.objects.create(note=note, attachment=mine, user_id=BOB))
    assert NoteImage.objects.create(note=note, attachment=mine, user_id=ALICE)


def test_a_note_version_must_carry_the_notes_owner():
    note = make_note(ALICE)
    refused(lambda: NoteVersion.objects.create(note=note, user_id=BOB, rev=1))
    assert NoteVersion.objects.create(note=note, user_id=ALICE, rev=1)


def test_an_annotation_must_belong_to_its_documents_owner():
    doc = make_document(ALICE)
    refused(lambda: make_annotation(doc, user_id=BOB))
    assert make_annotation(doc).pk


def test_a_page_range_and_an_export_must_belong_to_their_documents_owner(scheme):
    doc = make_document(ALICE)
    chapter = Chapter.objects.get(key="gst-itc")
    from modules.notes.services import links

    link = links.link_columns(chapter.id, None)
    refused(lambda: DocumentChapter.objects.create(user_id=BOB, document=doc, page_from=1, page_to=2, **link))
    refused(lambda: ExportJob.objects.create(user_id=BOB, document=doc))
    assert DocumentChapter.objects.create(user_id=ALICE, document=doc, page_from=1, page_to=2, **link).pk


def test_page_ranges_of_one_document_cannot_overlap(scheme):
    doc, other = make_document(ALICE), make_document(ALICE)
    from modules.notes.services import links

    link = links.link_columns(Chapter.objects.get(key="gst-itc").id, None)

    def add(document, a, b):
        return DocumentChapter.objects.create(user_id=ALICE, document=document, page_from=a, page_to=b, **link)

    add(doc, 1, 10)
    add(doc, 11, 20)  # touching is fine: [1,10] and [11,20] share no page
    add(doc, 30, 30)
    refused(lambda: add(doc, 10, 12))
    refused(lambda: add(doc, 5, 5))
    refused(lambda: add(doc, 25, 30))
    add(other, 1, 10)  # another document may use the same pages


def test_the_archive_export_has_no_document_but_a_pdf_export_needs_one():
    ExportJob.objects.create(user_id=ALICE, kind="archive")
    refused(lambda: ExportJob.objects.create(user_id=ALICE, kind="pdf"))


def test_deleting_parents_still_cascades_through_the_composite_keys():
    note, tag = make_note(ALICE), make_tag(ALICE)
    ItemTag.objects.create(user_id=ALICE, tag=tag, note=note)
    NoteVersion.objects.create(note=note, user_id=ALICE, rev=1)
    note.delete()
    assert not ItemTag.objects.exists() and not NoteVersion.objects.exists()

    doc = make_document(ALICE)
    mark = make_annotation(doc)
    ItemTag.objects.create(user_id=ALICE, tag=tag, annotation=mark)
    ItemTag.objects.create(user_id=ALICE, tag=tag, document=doc)
    ExportJob.objects.create(user_id=ALICE, document=doc)
    doc.delete()
    assert not Annotation.objects.exists() and not ItemTag.objects.exists() and not ExportJob.objects.exists()
    tag.delete()
    assert Tag.objects.count() == 0


def test_a_raw_delete_of_the_parent_cascades_in_the_database_itself():
    doc = make_document(ALICE)
    make_annotation(doc)
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM notes_document WHERE id = %s", [doc.pk])
    assert not Annotation.objects.exists() and not Document.objects.exists()


def test_the_page_search_index_and_extensions_exist():
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname = 'notes_filepage_search_idx'")
        (definition,) = cursor.fetchone()
        cursor.execute("SELECT extname FROM pg_extension WHERE extname IN ('btree_gin', 'btree_gist')")
        found = {row[0] for row in cursor.fetchall()}
    assert "gin" in definition and "content_id" in definition and "tsv" in definition
    assert found == {"btree_gin", "btree_gist"}
