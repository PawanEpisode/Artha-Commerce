"""Subject-level filing: a note or PDF under a subject with no chapter ("All chapters"), between Unfiled and a chapter."""

import uuid

import pytest

from modules.notes.models import Document, Note
from modules.notes.selectors._common import link_views
from modules.syllabus.models import Subject
from modules.syllabus.tests.helpers import make_scheme, switch_scheme

from .conftest import edit, new_note
from .documents_support import MB, reserve
from .factories import ALICE, make_document, make_note

pytestmark = pytest.mark.django_db


def agg(api, q):
    res = api.get(f"/notes/aggregate/?{q}")
    assert res.status_code == 200, res.json_body
    return {i["id"] for i in res.json_body["items"]}


def doc_ids(api, q):
    res = api.get(f"/notes/documents/?{q}")
    assert res.status_code == 200, res.json_body
    return {i["id"] for i in res.json_body["items"]}


def test_reserving_with_a_subject_files_the_document_at_subject_level(api, fake_storage, ids, level_id):
    res = reserve(api, MB, subject_id=ids["taxation"])
    assert res.status_code == 201, res.json_body
    link = res.json_body["document"]["link"]
    assert link["subject_id"] == ids["taxation"] and link["subject_key"] == "taxation"
    assert link["subject_name"] == "Taxation" and link["level_id"] == level_id
    assert link["chapter_id"] is None and link["chapter_key"] is None and link["topic_id"] is None
    assert link["moved_or_removed"] is False
    row = Document.objects.get(pk=res.json_body["document"]["id"])
    assert (row.subject_key, row.chapter_id, row.chapter_key, row.topic_id) == ("taxation", None, None, None)


def test_a_document_walks_chapter_to_subject_to_unfiled_and_back(api, fake_storage, ids):
    doc = make_document(ALICE)
    url = f"/notes/documents/{doc.id}/"
    on_chapter = api.patch(url, {"chapter_id": ids["gst"]}).json_body["link"]
    assert on_chapter["chapter_id"] == ids["gst"] and on_chapter["subject_key"] == "taxation"
    subject = api.patch(url, {"chapter_id": None, "subject_id": ids["taxation"]})
    assert subject.status_code == 200, subject.json_body
    link = subject.json_body["link"]
    assert link["subject_id"] == ids["taxation"] and link["chapter_id"] is None and link["chapter_key"] is None
    assert subject.json_body["rev"] == 3
    again = api.patch(url, {"subject_id": ids["taxation"]}).json_body  # same place: nothing changes
    assert again["rev"] == 3
    other = api.patch(url, {"subject_id": ids["laws"]}).json_body["link"]  # subject alone means subject level
    assert other["subject_key"] == "corporate-laws" and other["chapter_id"] is None
    unfiled = api.patch(url, {"chapter_id": None}).json_body["link"]  # chapter null alone: Unfiled, as before
    assert unfiled["subject_id"] is None and unfiled["subject_key"] is None and unfiled["level_id"] is None
    back = api.patch(url, {"subject_id": ids["taxation"]}).json_body["link"]
    assert back["subject_key"] == "taxation"
    assert api.patch(url, {"chapter_id": ids["gst"]}).json_body["link"]["chapter_key"] == "gst-itc"


def test_a_mismatched_subject_and_chapter_is_422(api, fake_storage, ids):
    doc = make_document(ALICE)
    res = api.patch(f"/notes/documents/{doc.id}/", {"chapter_id": ids["gst"], "subject_id": ids["laws"]})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "subject_chapter_mismatch"
    res = reserve(api, MB, chapter_id=ids["gst"], subject_id=ids["laws"])
    assert res.status_code == 422 and res.json_body["error"]["code"] == "subject_chapter_mismatch"
    ok = api.patch(f"/notes/documents/{doc.id}/", {"chapter_id": ids["gst"], "subject_id": ids["taxation"]})
    assert ok.status_code == 200 and ok.json_body["link"]["chapter_key"] == "gst-itc"
    assert Document.objects.get(pk=doc.id).chapter_key == "gst-itc"


def test_an_unknown_or_draft_subject_is_422_and_writes_nothing(api, fake_storage, ids):
    doc = make_document(ALICE)
    res = api.patch(f"/notes/documents/{doc.id}/", {"subject_id": str(uuid.uuid4())})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_subject"
    assert reserve(api, MB, subject_id=str(uuid.uuid4())).status_code == 422
    assert api.post("/notes/", {"client_id": str(uuid.uuid4()), "subject_id": str(uuid.uuid4())}).status_code == 422
    assert Document.objects.get(pk=doc.id).subject_id is None and Document.objects.count() == 1
    draft = make_scheme(publish=False, code="2030")
    draft_subject = Subject.objects.get(scheme=draft, key="taxation")
    res = api.post("/notes/", {"client_id": str(uuid.uuid4()), "subject_id": str(draft_subject.id)})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_subject"


def test_a_note_can_be_created_and_patched_at_subject_level(api, ids, level_id):
    n = new_note(api, "body", subject_id=ids["taxation"])
    link = n["link"]
    assert link["subject_key"] == "taxation" and link["subject_name"] == "Taxation" and link["level_id"] == level_id
    assert (link["chapter_id"], link["chapter_key"], link["topic_id"]) == (None, None, None)
    plain = new_note(api, "plain")
    assert plain["link"]["subject_id"] is None
    res = edit(api, plain, subject_id=ids["laws"])
    assert res.status_code == 200 and res.json_body["link"]["subject_key"] == "corporate-laws"
    res = edit(api, res.json_body, chapter_id=ids["gst"])
    assert res.json_body["link"]["chapter_key"] == "gst-itc" and res.json_body["link"]["subject_key"] == "taxation"
    res = edit(api, res.json_body, chapter_id=None, subject_id=ids["taxation"])
    assert res.json_body["link"]["chapter_id"] is None and res.json_body["link"]["subject_key"] == "taxation"
    res = edit(api, res.json_body, chapter_id=None)
    assert res.json_body["link"]["subject_id"] is None and res.json_body["link"]["level_id"] is None
    bad = edit(api, res.json_body, chapter_id=ids["gst"], subject_id=ids["laws"])
    assert bad.status_code == 422 and bad.json_body["error"]["code"] == "subject_chapter_mismatch"


def test_subject_level_items_are_filed_not_unfiled_and_not_in_a_chapter(api, fake_storage, ids, level_id):
    chapter_note = new_note(api, "c", chapter_id=ids["gst"])
    subject_note = new_note(api, "s", subject_id=ids["taxation"])
    unfiled_note = new_note(api, "u")
    other_subject = new_note(api, "o", subject_id=ids["laws"])
    subject_doc = make_document(ALICE, title="Subject PDF")
    api.patch(f"/notes/documents/{subject_doc.id}/", {"subject_id": ids["taxation"]})
    unfiled_doc = make_document(ALICE, title="Unfiled PDF")
    chapter_doc = make_document(ALICE, title="Chapter PDF")
    api.patch(f"/notes/documents/{chapter_doc.id}/", {"chapter_id": ids["gst"]})
    sid, did = subject_note["id"], str(subject_doc.id)

    assert agg(api, f"level={level_id}&subject=taxation") == {chapter_note["id"], sid, did, str(chapter_doc.id)}
    assert agg(api, f"level={level_id}&subject=corporate-laws") == {other_subject["id"]}
    assert agg(api, f"level={level_id}&subject=taxation&tab=documents") == {did, str(chapter_doc.id)}
    assert agg(api, "unfiled=true") == {unfiled_note["id"], str(unfiled_doc.id)}
    chapter_only = agg(api, f"level={level_id}&subject=taxation&chapter=gst-itc")
    assert chapter_only == {chapter_note["id"], str(chapter_doc.id)}
    assert doc_ids(api, f"level={level_id}&subject=taxation") == {did, str(chapter_doc.id)}
    assert doc_ids(api, f"level={level_id}&subject=taxation&chapter=gst-itc") == {str(chapter_doc.id)}
    notes = api.get(f"/notes/?level={level_id}&subject=taxation").json_body["items"]
    assert {i["id"] for i in notes} == {chapter_note["id"], sid}
    notes = api.get("/notes/?unfiled=true").json_body["items"]
    assert {i["id"] for i in notes} == {unfiled_note["id"]}


def test_counts_leave_subject_level_items_out_of_chapters_and_unfiled(api, ids, level_id):
    new_note(api, "u")
    new_note(api, "s", subject_id=ids["taxation"])
    new_note(api, "c", chapter_id=ids["gst"])
    res = api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation")
    assert res.status_code == 200, res.json_body
    body = res.json_body
    assert body["unfiled"] == 1
    assert sum(c["notes"] for c in body["chapters"]) == 1


def test_link_views_resolve_by_the_current_scheme_and_flag_a_removed_subject(scheme, ids):
    n = make_note(
        ALICE,
        **{
            "level_id": scheme.level_id,
            "subject_id": Subject.objects.get(scheme=scheme, key="taxation").id,
            "subject_key": "taxation",
        },
    )
    (view,) = link_views([n])
    assert (view.subject_key, view.subject_name, view.chapter_id, view.topic_id) == ("taxation", "Taxation", None, None)
    assert view.moved_or_removed is False
    switch_scheme(scheme, lambda spec: spec["subjects"].pop(0))
    (gone,) = link_views([Note.objects.get(pk=n.pk)])
    assert gone.subject_key == "taxation" and gone.subject_name == "Taxation" and gone.moved_or_removed is True


def test_marks_on_a_subject_level_document_stay_unfiled_and_relinking_does_not_crash(api, fake_storage, ids):
    from modules.notes.services import document_ranges

    from .factories import make_annotation

    doc = make_document(ALICE)
    api.patch(f"/notes/documents/{doc.id}/", {"chapter_id": ids["gst"]})
    mark = make_annotation(Document.objects.get(pk=doc.id))
    document_ranges.relink_marks(Document.objects.get(pk=doc.id))
    res = api.patch(f"/notes/documents/{doc.id}/", {"chapter_id": None, "subject_id": ids["taxation"]})
    assert res.status_code == 200
    mark.refresh_from_db()
    assert mark.chapter_id is None and mark.subject_id is None
