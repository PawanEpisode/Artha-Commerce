"""Replace edition: the new file takes the old one's place and the marks follow it; what is unsure waits for the student."""
# ruff: noqa: F811 - pytest fixtures imported from the support modules are redefined as test arguments

import uuid

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from core import jobs as core_jobs
from modules.coverage.tests.conftest import OTHER, USER
from modules.notes.models import Annotation, Document, FilePage, Note, ReanchorItem
from modules.notes.services import reanchor

from .ai_support import ai_on  # noqa: F401
from .factories import make_annotation
from .ocr_export_support import fake_storage, make_pdf_document  # noqa: F401

pytestmark = pytest.mark.django_db

LINE_A = "Input tax credit under GST is available on inward supplies used for business."
LINE_B = "Place of supply decides whether IGST or CGST and SGST are charged on the sale."
QUAD = {"quads": [[0.1, 0.1, 0.3, 0.02]]}


def pdf(path, pages):
    c = canvas.Canvas(str(path), pagesize=A4)
    for lines in pages:
        c.setFont("Helvetica", 14)
        y = 760
        for line in lines:
            c.drawString(72, y, line)
            y -= 40
        c.showPage()
    c.save()
    return path


def old_edition(fake, tmp_path):
    path = pdf(tmp_path / "old.pdf", [[LINE_A], [LINE_B], ["Closing remarks for the chapter."]])
    old = make_pdf_document(fake, USER, path, page_count=3)
    for n, text in enumerate([LINE_A, LINE_B, "Closing remarks for the chapter."], 1):
        FilePage.objects.create(content_id=old.content_id, page=n, text=text, text_source="native")
    return old


def new_edition(fake, tmp_path, old, pages):
    path = pdf(tmp_path / f"new-{uuid.uuid4().hex[:5]}.pdf", pages)
    new = make_pdf_document(fake, USER, path, page_count=len(pages))
    Document.objects.filter(pk=new.pk).update(replaces_document_id=old.id, reanchor_status="waiting")
    new.refresh_from_db()
    return new


def highlight(old, text, page, **kw):
    return make_annotation(
        old, kind="highlight", page=page, geometry=QUAD, quote_exact=text, comment=kw.pop("comment", "mine"), **kw
    )


def run(new):
    return reanchor.run_reanchor({"document_id": str(new.id)})


def test_a_highlight_follows_its_words_to_the_page_they_moved_to(fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    mark = highlight(old, "tax credit under GST", 1, seq=1)
    new = new_edition(fake_storage, tmp_path, old, [["Preface added in the new edition."], [LINE_A], [LINE_B]])
    result = run(new)
    assert result["total"] == 1 and result["moved"] == 1 and result["needs_attention"] == 0
    carried = Annotation.objects.get(pk=reanchor.carried_id(new.id, mark.id))
    assert carried.document_id == new.id and carried.page == 2 and carried.comment == "mine"
    assert carried.geometry["quads"] and carried.geometry != QUAD  # drawn around the new words, not copied
    new.refresh_from_db()
    assert new.reanchor_status == "done" and new.reanchor_stats["moved"] == 1
    assert Annotation.objects.filter(document=old, deleted_at__isnull=True).count() == 1  # the old edition is untouched


def test_a_quote_that_is_gone_waits_for_the_student_and_is_never_guessed(fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    highlight(old, "tax credit under GST", 1)
    new = new_edition(
        fake_storage, tmp_path, old, [["Entirely rewritten text about depreciation."], ["More."], ["End."]]
    )
    result = run(new)
    assert result["needs_attention"] == 1 and not Annotation.objects.filter(document=new).exists()
    item = ReanchorItem.objects.get(document=new)
    assert item.status == "open" and item.quote_exact == "tax credit under GST" and item.reason


def test_a_mark_that_is_not_text_follows_a_page_whose_text_did_not_change_and_waits_otherwise(fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    kept = make_annotation(old, kind="area", page=2, geometry={"rect": [0.1, 0.2, 0.2, 0.1]}, seq=1)
    lost = make_annotation(old, kind="sticky", page=1, geometry={"pt": [0.5, 0.5]}, seq=2)
    new = new_edition(
        fake_storage, tmp_path, old, [["A different first page now."], [LINE_B], ["Closing remarks for the chapter."]]
    )
    result = run(new)
    assert result["attached"] == 1 and result["needs_attention"] == 1
    assert Annotation.objects.filter(pk=reanchor.carried_id(new.id, kept.id)).exists()
    assert ReanchorItem.objects.get(document=new).source_annotation_id == lost.id


def test_a_retried_job_adds_nothing_twice(fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    highlight(old, "tax credit under GST", 1, seq=1)
    make_annotation(old, kind="sticky", page=1, geometry={"pt": [0.5, 0.5]}, seq=2)
    new = new_edition(fake_storage, tmp_path, old, [["Changed."], [LINE_A], [LINE_B]])
    run(new)
    Document.objects.filter(pk=new.pk).update(reanchor_status="waiting")
    run(new)
    assert (
        Annotation.objects.filter(document=new).count() == 1 and ReanchorItem.objects.filter(document=new).count() == 1
    )


def test_tags_of_a_mark_come_along(fake_storage, tmp_path):
    from modules.notes.models import ItemTag

    from .factories import make_tag

    old = old_edition(fake_storage, tmp_path)
    mark = highlight(old, "tax credit under GST", 1, seq=1)
    tag = make_tag(USER, "exam")
    ItemTag.objects.create(user_id=USER, annotation=mark, tag=tag)
    new = new_edition(fake_storage, tmp_path, old, [[LINE_A], [LINE_B], ["x"]])
    run(new)
    assert ItemTag.objects.filter(annotation_id=reanchor.carried_id(new.id, mark.id), tag=tag).exists()


def test_an_old_edition_in_the_trash_or_gone_fails_cleanly(fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    new = new_edition(fake_storage, tmp_path, old, [[LINE_A]])
    Document.objects.filter(pk=old.pk).delete()
    assert run(new) == {"skipped": "not_ready"}
    new.refresh_from_db()
    assert new.reanchor_status == "failed"


# --- The student decides -------------------------------------------------------------------------------------------------
@pytest.fixture
def waiting(fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    highlight(old, "tax credit under GST", 1, comment="remember this")
    new = new_edition(fake_storage, tmp_path, old, [["Rewritten."], ["More."], ["End."]])
    run(new)
    return new, ReanchorItem.objects.get(document=new)


def test_keep_puts_the_mark_on_the_new_edition_where_it_was_and_can_be_repeated(waiting):
    new, item = waiting
    kept = reanchor.resolve_item(USER, new.id, item.id, action="keep")
    assert kept.status == "kept" and Annotation.objects.get(pk=kept.new_annotation_id).document_id == new.id
    again = reanchor.resolve_item(USER, new.id, item.id, action="keep")
    assert again.new_annotation_id == kept.new_annotation_id
    assert Annotation.objects.filter(document=new).count() == 1


def test_a_page_outside_the_new_edition_is_refused(waiting):
    from modules.notes.errors_replace import PageOutOfRange

    new, item = waiting
    with pytest.raises(PageOutOfRange):
        reanchor.resolve_item(USER, new.id, item.id, action="keep", page=99)


def test_note_saves_the_quote_and_comment_as_a_note_once(waiting):
    new, item = waiting
    done = reanchor.resolve_item(USER, new.id, item.id, action="note")
    note = Note.objects.get(pk=done.result_note_id)
    assert "tax credit under GST" in note.body_md and "remember this" in note.body_md
    reanchor.resolve_item(USER, new.id, item.id, action="note")
    assert Note.objects.filter(user_id=USER).count() == 1


def test_dismiss_forgets_it_and_a_different_decision_after_is_a_conflict(waiting):
    from modules.notes.errors_replace import AlreadyResolved

    new, item = waiting
    assert reanchor.resolve_item(USER, new.id, item.id, action="dismiss").status == "dismissed"
    with pytest.raises(AlreadyResolved):
        reanchor.resolve_item(USER, new.id, item.id, action="keep")


# --- Over HTTP -------------------------------------------------------------------------------------------------------------
def test_every_route_is_closed_until_the_ai_flag_is_on(api, fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    url = f"/notes/documents/{old.id}/"
    body = {"client_id": str(uuid.uuid4()), "filename": "n.pdf", "bytes": 1000, "mime": "application/pdf"}
    assert api.post(url + "replace/", body).status_code == 403
    assert api.get(url + "attention/").status_code == 403
    assert api.post(url + f"attention/{uuid.uuid4()}/", {"action": "dismiss"}).status_code == 403


def test_replace_reserves_a_new_edition_that_remembers_the_old_one(api, ai_on, fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    body = {
        "client_id": str(uuid.uuid4()),
        "filename": "GST 2026.pdf",
        "bytes": 5000,
        "mime": "application/pdf",
        "edition_label": "2026 edition",
    }
    res = api.post(f"/notes/documents/{old.id}/replace/", body)
    assert res.status_code == 201, res.json_body
    doc = res.json_body["document"]
    assert doc["replaces_document_id"] == str(old.id) and doc["reanchor_status"] == "waiting"
    assert doc["edition_label"] == "2026 edition" and res.json_body["upload"]
    again = api.post(f"/notes/documents/{old.id}/replace/", body)
    assert again.status_code == 200 and again.json_body["document"]["id"] == doc["id"]  # same client id: same answer


def test_a_document_in_the_trash_cannot_be_replaced(api, ai_on, fake_storage, tmp_path):
    from django.utils import timezone

    old = old_edition(fake_storage, tmp_path)
    Document.objects.filter(pk=old.pk).update(deleted_at=timezone.now())
    body = {"client_id": str(uuid.uuid4()), "filename": "n.pdf", "bytes": 1000, "mime": "application/pdf"}
    res = api.post(f"/notes/documents/{old.id}/replace/", body)
    assert (res.status_code, res.json_body["error"]["code"]) == (409, "not_replaceable")


def test_the_list_and_the_decisions_work_over_http_and_stay_private(api, ai_on, waiting):
    new, item = waiting
    got = api.get(f"/notes/documents/{new.id}/attention/").json_body
    assert got["status"] == "done" and got["stats"]["needs_attention"] == 1
    assert got["items"][0]["id"] == str(item.id) and got["items"][0]["quote"] == "tax credit under GST"
    res = api.post(f"/notes/documents/{new.id}/attention/{item.id}/", {"action": "dismiss"})
    assert res.status_code == 200 and res.json_body["status"] == "dismissed"
    conflict = api.post(f"/notes/documents/{new.id}/attention/{item.id}/", {"action": "keep"})
    assert (conflict.status_code, conflict.json_body["error"]["code"]) == (409, "already_resolved")
    assert api.get(f"/notes/documents/{new.id}/attention/?status=open").json_body["items"] == []


def test_another_student_sees_nothing(api, ai_on, fake_storage, tmp_path):
    other = Document.objects.create(
        user_id=OTHER, attachment=old_edition(fake_storage, tmp_path).attachment, title="x", status="ready", bytes=1
    )
    assert api.get(f"/notes/documents/{other.id}/attention/").status_code == 404
    body = {"client_id": str(uuid.uuid4()), "filename": "n.pdf", "bytes": 1000, "mime": "application/pdf"}
    assert api.post(f"/notes/documents/{other.id}/replace/", body).status_code == 404


def test_the_inspection_queues_the_job_when_a_new_edition_becomes_ready(fake_storage, tmp_path):
    old = old_edition(fake_storage, tmp_path)
    new = new_edition(fake_storage, tmp_path, old, [[LINE_A]])
    reanchor.queue_reanchor(new)
    reanchor.queue_reanchor(new)
    assert core_jobs.run_pending(types=["notes.reanchor"], worker="test") == 1  # one job however often it is asked
