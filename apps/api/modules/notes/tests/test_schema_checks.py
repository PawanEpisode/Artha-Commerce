"""The R2 tables' check constraints and the search vectors of pages and marks. Runs on SQLite and PostgreSQL."""

import pytest
from django.db import IntegrityError, connection, transaction

from modules.notes.domain import search_query
from modules.notes.models import Annotation, Document, ExportJob, FileContent, FilePage
from modules.notes.services import search_index

from .factories import ALICE, make_annotation, make_attachment, make_content, make_document

pytestmark = pytest.mark.django_db


def refused(create):
    with pytest.raises(IntegrityError), transaction.atomic():
        create()


def test_a_mark_stays_within_its_limits():
    doc = make_document(ALICE)
    refused(lambda: make_annotation(doc, page=0))
    refused(lambda: make_annotation(doc, page=5001))
    refused(lambda: make_annotation(doc, kind="laser"))
    refused(lambda: make_annotation(doc, color="zz"))
    refused(lambda: make_annotation(doc, comment="x" * 2001))
    refused(lambda: make_annotation(doc, quote_exact="x" * 1001))
    refused(lambda: make_annotation(doc, geometry={"pad": "x" * 70_000}))
    refused(lambda: make_annotation(doc, chapter_source="guess"))
    refused(lambda: make_annotation(doc, rev=0))
    ok = make_annotation(doc, comment="x" * 2000, quote_exact="y" * 1000, color="i3", kind="ink")
    assert Annotation.objects.get(pk=ok.pk).comment == "x" * 2000


def test_a_document_stays_within_its_limits():
    attachment = make_attachment(ALICE)
    base = {"user_id": ALICE, "title": "t", "attachment": attachment, "bytes": 1}
    refused(lambda: Document.objects.create(**{**base, "status": "open"}))
    refused(lambda: Document.objects.create(**{**base, "status_reason": "because"}))
    refused(lambda: Document.objects.create(**{**base, "marks_count": 20001}))
    refused(lambda: Document.objects.create(**{**base, "marks_count": -1}))
    refused(lambda: Document.objects.create(**{**base, "origin": "platform"}))  # a platform document has bytes = 0
    refused(lambda: Document.objects.create(**{**base, "page_tone": "neon"}))
    refused(lambda: Document.objects.create(**{**base, "purge_after": "2030-01-01T00:00:00Z"}))
    assert Document.objects.create(**{**base, "origin": "platform", "bytes": 0}).pk


def test_a_client_id_creates_one_document_per_student():
    import uuid

    cid = uuid.uuid4()
    make_document(ALICE, client_id=cid)
    refused(lambda: make_document(ALICE, client_id=cid))


def test_content_is_unique_by_hash_and_stays_within_limits():
    make_content(sha256="a" * 64)
    refused(lambda: make_content(sha256="a" * 64))
    refused(lambda: make_content(text_status="weird"))
    refused(lambda: make_content(text_pct=101))
    refused(lambda: make_content(ocr_status="halfway"))
    assert FileContent.objects.count() == 1


def test_an_export_job_stays_within_its_limits():
    doc = make_document(ALICE)
    refused(lambda: ExportJob.objects.create(user_id=ALICE, document=doc, progress=101))
    refused(lambda: ExportJob.objects.create(user_id=ALICE, document=doc, status="paused"))
    refused(lambda: ExportJob.objects.create(user_id=ALICE, document=doc, error_code="boom"))


def test_the_language_rule_has_a_sharp_boundary():
    # 30% Devanagari is still Latin text (english); anything over 30% needs the simple configuration
    assert search_query.config_for_text("abcdefgकखग") == "english"  # 7 Latin, 3 Devanagari: exactly 30%
    assert search_query.config_for_text("abcdefकखगघ") == "simple"  # 6 Latin, 4 Devanagari: 40%
    assert search_query.config_for_text("input tax credit") == "english"
    assert search_query.config_for_text("आगत कर क्रेडिट") == "simple"
    assert search_query.config_for_text("") == "english"


def test_page_language_is_set_for_each_page_and_vectors_follow_on_postgres():
    content = make_content()
    FilePage.objects.create(content=content, page=1, text="Input tax credit is allowed under section 16")
    FilePage.objects.create(content=content, page=2, text="आगत कर क्रेडिट धारा सोलह के अंतर्गत")
    FilePage.objects.create(content=content, page=3, text="Not refreshed yet")
    assert search_index.refresh_pages(content.pk, [1, 2]) == 2
    langs = dict(FilePage.objects.filter(content=content).values_list("page", "lang"))
    assert langs == {1: "en", 2: "hi", 3: "en"}  # page 3 keeps its default: it was not part of the chunk
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT page, tsv @@ plainto_tsquery('english', 'credits') FROM notes_filepage "
                "WHERE content_id = %s ORDER BY page",
                [content.pk],
            )
            assert [row[1] for row in cursor.fetchall()] == [True, False, None]
            cursor.execute(
                "SELECT tsv @@ plainto_tsquery('simple', 'क्रेडिट') FROM notes_filepage WHERE content_id = %s AND page = 2",
                [content.pk],
            )
            assert cursor.fetchone()[0] is True
    assert search_index.refresh_pages(content.pk) == 3  # all pages


@pytest.mark.skipif(connection.vendor != "postgresql", reason="stored vectors are PostgreSQL only")
def test_a_mark_is_found_by_its_quote_or_its_comment():
    doc = make_document(ALICE)
    mark = make_annotation(doc, quote_exact="Time of supply of goods", comment="revise before the mock")
    search_index.refresh_annotation(mark)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT search_tsv @@ plainto_tsquery('english', 'supplies'), search_tsv @@ plainto_tsquery('english', 'mock'), "
            "search_tsv @@ plainto_tsquery('english', 'invoice') FROM notes_annotation WHERE id = %s",
            [mark.pk],
        )
        assert cursor.fetchone() == (True, True, False)
