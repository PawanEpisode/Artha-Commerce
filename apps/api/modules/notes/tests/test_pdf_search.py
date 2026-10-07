"""Searching the text of PDFs (one document, the whole library) and the student's marks: ranking, limits, privacy, reasons."""

import pytest
from django.db import connection

from modules.coverage.tests.conftest import OTHER
from modules.notes.models import FileContent, FilePage
from modules.notes.services import search_index

from .factories import ALICE, make_annotation, make_content, make_document, make_note

pytestmark = pytest.mark.django_db


def indexed(texts, user=ALICE, **content_fields):
    """A ready document whose content has one stored, indexed page per text (page numbers from 1)."""
    content = make_content(page_count=len(texts), text_status="done", text_pages_done=len(texts), **content_fields)
    FilePage.objects.bulk_create(FilePage(content=content, page=n, text=t) for n, t in enumerate(texts, 1))
    search_index.refresh_pages(content.pk)
    return make_document(user, content=content, page_count=len(texts), title=f"Doc {content.pk.hex[:4]}")


def pdf(api, q, **extra):
    query = "&".join(f"{k}={v}" for k, v in extra.items())
    return api.get(f"/notes/search/?scope=pdf&q={q}" + (f"&{query}" if query else ""))


def test_in_document_search_ranks_pages_and_cuts_a_snippet_around_the_match(api, fake_storage):
    doc = indexed(
        [
            "Introduction to indirect taxes and the scheme of the Act.",
            "Input tax credit is available on inward supplies. " * 4 + "Blocked credit is listed separately.",
            "Nothing relevant here at all.",
            "Credit note and debit note rules; credit must be reversed in time.",
        ]
    )
    res = api.get(f"/notes/documents/{doc.id}/search/?q=credit")
    assert res.status_code == 200
    body = res.json_body
    assert {i["page"] for i in body["items"]} == {2, 4} and body["indexed_pages"] == 4 and body["page_count"] == 4
    assert body["text_status"] == "done" and body["ocr_status"] == "none"
    assert all("credit" in i["snippet"].lower() and "<" not in i["snippet"] for i in body["items"])
    assert all(i["rank"] > 0 for i in body["items"]) and body["items"][0]["rank"] >= body["items"][1]["rank"]
    assert api.get(f"/notes/documents/{doc.id}/search/?q=credit&limit=1").json_body["items"].__len__() == 1


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="phrase matching is full text search; SQLite matches substrings"
)
def test_references_are_matched_as_phrases(api, fake_storage):
    doc = indexed(
        [
            "Credit of tax on goods used for personal consumption is blocked under section 17(5) of the CGST Act.",
            "Sections 17 and 5 of the other Act are unrelated; see paragraph 5 of schedule 17.",
            "Revenue is recognised under Ind AS 115 when control transfers.",
            "Ind AS 116 deals with leases; 115 is mentioned only as a number.",
        ]
    )
    pages = lambda q: [i["page"] for i in api.get(f"/notes/documents/{doc.id}/search/?q={q}").json_body["items"]]  # noqa: E731
    assert pages("17(5)") == [1]
    assert pages("Ind%20AS%20115") == [3]
    assert pages("section%2017(5)") == [1]


def test_hindi_pages_are_found_with_the_simple_configuration(api, fake_storage):
    doc = indexed(["यह अध्याय माल और सेवा कर के बारे में है।", "English only page about tax."])
    assert [i["page"] for i in api.get(f"/notes/documents/{doc.id}/search/?q=सेवा").json_body["items"]] == [1]


def test_in_document_search_validates_and_handles_an_unprepared_file(api, fake_storage):
    doc = indexed(["text"])
    assert api.get(f"/notes/documents/{doc.id}/search/").status_code == 400
    assert api.get(f"/notes/documents/{doc.id}/search/?q=x&limit=51").status_code == 400
    fresh = make_document(ALICE, status="inspecting")
    body = api.get(f"/notes/documents/{fresh.id}/search/?q=credit").json_body
    assert body["items"] == [] and body["text_status"] == "pending" and body["indexed_pages"] == 0


def test_library_search_groups_hits_by_document_with_at_most_five_pages_each(api, fake_storage):
    many = indexed([f"Page {n} explains input tax credit in detail" for n in range(1, 9)])
    few = indexed(["A single mention of credit"])
    other = indexed(["Unrelated text about depreciation"])
    body = pdf(api, "credit").json_body
    by_doc = {}
    for hit in body["items"]:
        by_doc.setdefault(hit["document_id"], []).append(hit)
    assert set(by_doc) == {str(many.id), str(few.id)} and len(by_doc[str(many.id)]) == 5 and str(other.id) not in by_doc
    first = body["items"][0]
    assert first["type"] == "pdf" and first["document_title"] and first["page"] >= 1 and first["snippet"]
    assert first["link"]["chapter_id"] is None and first["rank"] > 0 and body["next_cursor"] is None
    ranks = [h["rank"] for h in body["items"]]
    assert ranks == sorted(ranks, reverse=True)


def test_library_search_returns_at_most_a_hundred_hits(api, fake_storage):
    for _ in range(25):
        indexed([f"credit appears on page {n}" for n in range(1, 6)])
    assert len(pdf(api, "credit").json_body["items"]) == 100


def test_trashed_other_students_and_duplicate_documents_do_not_answer(api, other_api, fake_storage):
    from django.utils import timezone

    content = make_content(page_count=1, text_status="done", text_pages_done=1)
    FilePage.objects.create(content=content, page=1, text="credit in a shared file")
    search_index.refresh_pages(content.pk)
    first = make_document(ALICE, content=content, page_count=1)
    make_document(ALICE, content=content, page_count=1)  # a second copy: one answer, not two
    theirs = make_document(OTHER, content=content, page_count=1)
    binned = indexed(["credit in a trashed document"])
    binned.deleted_at = timezone.now()
    binned.save()
    mine = pdf(api, "credit").json_body["items"]
    assert [(h["document_id"], h["page"]) for h in mine] == [(str(first.id), 1)]
    assert [h["document_id"] for h in pdf(other_api, "credit").json_body["items"]] == [str(theirs.id)]


def test_documents_that_cannot_be_searched_are_listed_with_the_reason(api, fake_storage):
    ready = indexed(["credit"])
    locked = make_document(
        ALICE, status="needs_password", content=make_content(text_status="locked", is_encrypted=True)
    )
    scanned = make_document(
        ALICE, content=make_content(page_count=3, text_status="done", is_scanned=True, ocr_status="none"), page_count=3
    )
    ocr_running = make_document(
        ALICE,
        content=make_content(page_count=3, text_status="done", is_scanned=True, ocr_status="running"),
        page_count=3,
    )
    ocr_done = make_document(
        ALICE, content=make_content(page_count=3, text_status="done", is_scanned=True, ocr_status="done"), page_count=3
    )
    extracting = make_document(
        ALICE, content=make_content(page_count=9, text_status="running", text_pages_done=3), page_count=9
    )
    waiting = make_document(ALICE, status="inspecting", page_count=None)
    meta = pdf(api, "credit").json_body["meta"]
    reasons = {n["document_id"]: n["reason"] for n in meta["not_searchable"]}
    assert reasons == {
        str(locked.id): "locked",
        str(scanned.id): "scanned",
        str(ocr_running.id): "pending",
        str(extracting.id): "pending",
        str(waiting.id): "pending",
    }
    assert meta["indexing_documents"] == 3 and str(ready.id) not in reasons and str(ocr_done.id) not in reasons


def test_a_document_still_being_extracted_is_searchable_for_the_pages_done(api, fake_storage):
    doc = indexed(["credit on the first pages"])
    FileContent.objects.filter(pk=doc.content_id).update(text_status="running", text_pages_done=1, page_count=10)
    body = pdf(api, "credit").json_body
    assert len(body["items"]) == 1 and body["meta"]["indexing_documents"] == 1


def test_marks_are_found_by_their_quote_or_comment_text_kinds_and_live_only(api, other_api, fake_storage, chapter):
    doc = indexed(["page"])
    from modules.notes.services import links

    wanted = make_annotation(
        doc,
        quote_exact="Input tax credit is blocked for motor cars",
        page=4,
        color="g",
        **links.link_columns(chapter.id),
    )
    by_comment = make_annotation(
        doc, kind="sticky", comment="Remember the blocked credit list", page=7, color="p", quote_exact=None
    )
    hidden = [
        make_annotation(doc, quote_exact="blocked credit but a tombstone", deleted_at=chapter.created_at),
        make_annotation(doc, kind="ink", quote_exact="blocked credit scribble"),
        make_annotation(doc, kind="bookmark", comment="blocked credit bookmark", color=None),
        make_annotation(doc, quote_exact="nothing to see"),
    ]
    stranger = make_document(OTHER, content=make_content())
    make_annotation(stranger, quote_exact="blocked credit of someone else")
    trashed = make_document(ALICE, content=make_content(), deleted_at=chapter.created_at)
    make_annotation(trashed, quote_exact="blocked credit in a trashed document")
    for mark in [wanted, by_comment, *hidden]:
        search_index.refresh_annotation(mark)
    body = api.get("/notes/search/?scope=highlights&q=blocked%20credit").json_body
    got = {h["annotation_id"]: h for h in body["items"]}
    assert set(got) == {str(wanted.id), str(by_comment.id)} and "meta" not in body
    row = got[str(wanted.id)]
    assert (row["type"], row["document_id"], row["page"], row["color"]) == ("highlight", str(doc.id), 4, "g")
    assert "blocked" in row["snippet"].lower() and row["link"]["chapter_key"] == "gst-itc" and row["document_title"]


def test_scope_all_adds_pdf_pages_and_marks_after_the_notes_on_the_first_page(api, fake_storage):
    note = make_note(ALICE, title="Credit rules", body_text="credit notes", body_md="credit notes", body_chars=12)
    search_index.refresh(note)
    doc = indexed(["credit in the pdf"])
    mark = make_annotation(doc, quote_exact="credit in a highlight")
    search_index.refresh_annotation(mark)
    body = api.get("/notes/search/?scope=all&q=credit").json_body
    assert [i["type"] for i in body["items"]] == ["note", "highlight", "pdf"]
    assert set(body["meta"]) == {"indexing_documents", "not_searchable"}
    assert [i["type"] for i in api.get("/notes/search/?scope=notes&q=credit").json_body["items"]] == ["note"]
    assert "meta" not in api.get("/notes/search/?scope=notes&q=credit").json_body


def test_the_pdf_scope_is_closed_when_the_flag_is_off_and_all_falls_back_to_notes(api, pdf_flag_off, fake_storage):
    res = api.get("/notes/search/?scope=pdf&q=credit")
    assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"
    off = api.get("/notes/search/?scope=all&q=credit").json_body
    assert off["items"] == [] and "meta" not in off
    assert api.get("/notes/search/?scope=highlights&q=credit").json_body["items"] == []


def test_the_search_filters_by_syllabus_and_validates(api, fake_storage, scheme):
    from modules.notes.services import links
    from modules.syllabus.models import Chapter

    filed = indexed(["credit in a filed document"])
    for column, value in links.link_columns(Chapter.objects.get(key="gst-itc").id).items():
        setattr(filed, column, value)
    filed.save()
    indexed(["credit in an unfiled document"])
    level = str(scheme.level_id)
    assert [
        h["document_id"]
        for h in pdf(api, "credit", level=level, subject="taxation", chapter="gst-itc").json_body["items"]
    ] == [str(filed.id)]
    assert api.get("/notes/search/?scope=pdf").status_code == 400
    assert api.get("/notes/search/?scope=pdf&q=" + "x" * 201).status_code == 400
    assert api.get("/notes/search/?scope=everything&q=a").status_code == 400
    assert pdf(api, "%20%20").status_code == 400  # a blank query is not a search


def test_the_search_needs_a_signed_in_student(client):
    assert client.get("/api/v1/notes/search/?scope=pdf&q=credit").status_code == 401
