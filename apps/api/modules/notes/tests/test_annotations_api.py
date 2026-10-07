"""Marks over HTTP: create, edit, delete, restore, the delta feed, validation, ownership, and the flags."""

import uuid

import pytest

from core import feature_flags
from modules.notes.models import Annotation, Document
from modules.notes.services import quota

from .marks_support import OTHER, USER, body, create, delta, edit, new_document, put, remove

pytestmark = pytest.mark.django_db


def test_create_returns_201_with_the_annotation_shape(api):
    doc = new_document()
    res, mark_id = put(
        api,
        doc,
        comment="why",
        quote_exact="Input tax credit",
        quote_prefix="the ",
        text_start=4,
        text_end=20,
        anchor_engine="pdfjs",
    )
    assert res.status_code == 201
    a = res.json_body["annotation"]
    assert a["id"] == mark_id and a["document_id"] == str(doc.id) and a["rev"] == 1 and a["seq"] == 1
    assert set(a) == {
        "id", "document_id", "page", "kind", "geometry", "color", "comment", "quote_exact", "quote_prefix", "quote_suffix",
        "text_start", "text_end", "anchor_engine", "link", "chapter_source", "tags", "recall_card_id", "rev", "seq",
        "device_id", "created_at", "updated_at", "deleted_at",
    }  # fmt: skip
    assert (
        a["geometry"] == {"quads": [[0.1, 0.1, 0.3, 0.02]]}
        and a["chapter_source"] == "none"
        and a["link"]["chapter_id"] is None
    )
    assert a["recall_card_id"] is None and a["tags"] == [] and a["deleted_at"] is None
    assert (res.json_body["merged"], res.json_body["restored"], res.json_body["overwritten"]) == (False, False, [])
    assert res.json_body["change_seq"] == 1 and res.json_body["marks"] == {
        "count": 1,
        "limit": 20000,
        "near_limit": False,
    }
    doc.refresh_from_db()
    assert (doc.change_seq, doc.marks_count) == (1, 1)


def test_a_duplicate_create_returns_the_stored_row_with_200_and_changes_nothing(api):
    doc = new_document()
    res, mark_id = put(api, doc, comment="first")
    again = api.put(f"/notes/annotations/{mark_id}/", {**body(doc), "comment": "a replay with other words"})
    assert again.status_code == 200
    assert again.json_body["annotation"]["comment"] == "first" and again.json_body["annotation"]["rev"] == 1
    doc.refresh_from_db()
    assert (doc.change_seq, doc.marks_count) == (1, 1)  # no seq burned, no second count


def test_edit_delete_restore_keep_seq_rev_and_the_counter_in_step(api):
    doc = new_document()
    mark = create(api, doc)
    res = edit(api, mark, comment="edited", color="g")
    assert (
        res.status_code == 200 and res.json_body["annotation"]["rev"] == 2 and res.json_body["annotation"]["seq"] == 2
    )
    gone = remove(api, mark["id"], base_rev=2)
    assert gone.status_code == 200 and gone.json_body["edit_wins"] is False
    tomb = gone.json_body["annotation"]
    assert tomb["deleted_at"] and tomb["rev"] == 3 and tomb["seq"] == 3
    assert Annotation.objects.get(pk=mark["id"]).purge_after is not None
    doc.refresh_from_db()
    assert (doc.change_seq, doc.marks_count) == (3, 0)
    back = api.post(f"/notes/annotations/{mark['id']}/restore/")
    assert back.status_code == 200 and back.json_body["restored"] is True
    assert back.json_body["annotation"]["deleted_at"] is None and back.json_body["annotation"]["rev"] == 4
    doc.refresh_from_db()
    assert (doc.change_seq, doc.marks_count) == (4, 1)
    assert (
        api.post(f"/notes/annotations/{mark['id']}/restore/").json_body["annotation"]["rev"] == 4
    )  # a live mark: idempotent
    assert remove(api, mark["id"], base_rev=4).status_code == 200
    again = remove(api, mark["id"], base_rev=4)  # delete versus delete
    assert (
        again.status_code == 200 and again.json_body["annotation"]["rev"] == 5 and again.json_body["edit_wins"] is False
    )


def test_replaying_an_accepted_edit_changes_nothing(api):
    doc = new_document()
    mark = create(api, doc, comment="a")
    first = edit(api, mark, comment="b", base={"comment": "a"})
    again = edit(api, mark, comment="b", base={"comment": "a"})  # the same write after a lost response
    assert first.json_body["annotation"]["rev"] == 2 and again.status_code == 200
    assert again.json_body["annotation"]["rev"] == 2 and again.json_body["annotation"]["comment"] == "b"
    doc.refresh_from_db()
    assert doc.change_seq == 2


def test_the_delta_feed_returns_tombstones_in_seq_order_and_pages(api):
    doc = new_document()
    marks = [create(api, doc, comment=str(i)) for i in range(5)]
    remove(api, marks[1]["id"], base_rev=1)  # seq 6
    edit(api, marks[0], comment="again")  # seq 7
    whole = delta(api, doc)
    seqs = [a["seq"] for a in whole["items"]]
    assert seqs == [3, 4, 5, 6, 7]
    assert [a["id"] for a in whole["items"]] == [
        marks[2]["id"],
        marks[3]["id"],
        marks[4]["id"],
        marks[1]["id"],
        marks[0]["id"],
    ]
    assert whole["change_seq"] == 7 and whole["has_more"] is False and whole["next_since_seq"] == 7
    assert any(a["deleted_at"] for a in whole["items"])
    first = delta(api, doc, since=0, limit=2)
    assert (
        len(first["items"]) == 2 and first["has_more"] is True and first["next_since_seq"] == first["items"][-1]["seq"]
    )
    second = delta(api, doc, since=first["next_since_seq"], limit=2)
    third = delta(api, doc, since=second["next_since_seq"], limit=2)
    paged = [a["id"] for a in first["items"] + second["items"] + third["items"]]
    assert paged == [a["id"] for a in whole["items"]] and third["has_more"] is False
    assert delta(api, doc, since=7)["items"] == [] and delta(api, doc, since=7)["next_since_seq"] == 7


def test_a_mark_inherits_the_documents_default_chapter_and_an_explicit_one_wins(api, scheme):
    from modules.syllabus.models import Chapter

    gst, heads = Chapter.objects.get(key="gst-itc"), Chapter.objects.get(key="heads-of-income")
    from modules.notes.services import links

    doc = new_document(**links.link_columns(gst.id))
    inherited = create(api, doc)
    assert inherited["chapter_source"] == "document" and inherited["link"]["chapter_key"] == "gst-itc"
    chosen = create(api, doc, chapter_id=str(heads.id))
    assert chosen["chapter_source"] == "explicit" and chosen["link"]["chapter_key"] == "heads-of-income"
    cleared = edit(api, chosen, chapter_id=None, base={"chapter_id": str(heads.id)}).json_body["annotation"]
    assert cleared["chapter_source"] == "document" and cleared["link"]["chapter_key"] == "gst-itc"
    assert api.put(f"/notes/annotations/{uuid.uuid4()}/", body(doc, chapter_id=str(uuid.uuid4()))).status_code == 422


def test_invalid_geometry_is_422_and_nothing_is_written(api):
    doc = new_document()
    res = api.put(f"/notes/annotations/{uuid.uuid4()}/", {**body(doc), "geometry": {"quads": [[0.5, 0.5, 0.9, 0.9]]}})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "invalid_geometry"
    assert res.json_body["error"]["details"]["errors"][0]["code"] == "out_of_range"
    wrong = api.put(f"/notes/annotations/{uuid.uuid4()}/", {**body(doc), "kind": "area"})  # quads for an area
    assert wrong.status_code == 422 and wrong.json_body["error"]["code"] == "invalid_geometry"
    assert Annotation.objects.count() == 0
    doc.refresh_from_db()
    assert (doc.change_seq, doc.marks_count) == (0, 0)


def test_field_validation_and_a_page_outside_the_document(api):
    doc = new_document(page_count=3)
    assert api.put(f"/notes/annotations/{uuid.uuid4()}/", {**body(doc), "page": 0}).status_code == 400
    assert api.put(f"/notes/annotations/{uuid.uuid4()}/", {**body(doc), "color": "zz"}).status_code == 400
    assert api.put(f"/notes/annotations/{uuid.uuid4()}/", {**body(doc), "comment": "x" * 2001}).status_code == 400
    assert api.put(f"/notes/annotations/{uuid.uuid4()}/", {**body(doc)} | {"kind": "pen"}).status_code == 400
    assert (
        api.put(
            f"/notes/annotations/{uuid.uuid4()}/", {k: v for k, v in body(doc).items() if k != "document_id"}
        ).status_code
        == 400
    )
    far = api.put(f"/notes/annotations/{uuid.uuid4()}/", {**body(doc), "page": 4})
    assert far.status_code == 422 and far.json_body["error"]["code"] == "invalid_mark"
    no_geometry = api.put(
        f"/notes/annotations/{uuid.uuid4()}/", {k: v for k, v in body(doc).items() if k != "geometry"}
    )
    assert no_geometry.status_code == 400
    mark = create(api, doc)
    assert edit(api, mark, kind="area").status_code == 422  # a mark never changes kind


def test_the_marks_limit_is_429_with_a_95_percent_notice(api):
    doc = new_document()
    from modules.notes.models import QuotaPlan

    QuotaPlan.objects.filter(plan_code="free").update(max_marks_per_document=20)
    notices = []
    for _ in range(20):
        res, _ = put(api, doc)
        assert res.status_code == 201
        notices.append(res.json_body["marks"]["near_limit"])
    assert notices[:18] == [False] * 18 and notices[18:] == [True, True]  # 19 of 20 is 95%
    full, _ = put(api, doc)
    assert full.status_code == 429 and full.json_body["error"]["code"] == "quota_exceeded"
    assert full.json_body["error"]["details"] == {"kind": "marks", "used": 20, "limit": 20, "plan": "free"}
    doc.refresh_from_db()
    assert (doc.change_seq, doc.marks_count) == (20, 20)
    # a trashed mark frees a slot
    first = delta(api, doc)["items"][0]
    remove(api, first["id"], base_rev=1)
    assert put(api, doc)[0].status_code == 201
    assert quota.max_marks_per_document(USER) == 20


def test_tags_on_marks_and_a_foreign_tag_is_refused(api, other_api):
    doc = new_document()
    mine = api.post("/notes/tags/", {"name": "revise"}).json_body
    theirs = other_api.post("/notes/tags/", {"name": "secret"}).json_body
    mark = create(api, doc, tag_ids=[mine["id"]])
    assert [t["id"] for t in mark["tags"]] == [mine["id"]]
    assert api.get("/notes/tags/").json_body["items"][0]["count"] == 1
    bad = api.put(f"/notes/annotations/{uuid.uuid4()}/", body(doc, tag_ids=[theirs["id"]]))
    assert bad.status_code == 422 and bad.json_body["error"]["code"] == "unknown_tag"
    assert Annotation.objects.count() == 1
    assert edit(api, mark, tag_ids=[theirs["id"]]).status_code == 422
    cleared = edit(api, mark, tag_ids=[]).json_body["annotation"]
    assert cleared["tags"] == [] and cleared["rev"] == 2
    remove(api, mark["id"], base_rev=2)
    assert api.get("/notes/tags/").json_body["items"][0]["count"] == 0


# --- ownership and auth -------------------------------------------------------------------------------------------------------
def test_everything_about_someone_elses_document_or_mark_is_404(api, other_api):
    doc = new_document(OTHER)
    mine = new_document(USER)
    theirs = create(other_api, doc)
    mark_id = theirs["id"]
    assert api.get(f"/notes/documents/{doc.id}/annotations/").status_code == 404
    assert api.put(f"/notes/annotations/{uuid.uuid4()}/", body(doc)).status_code == 404  # writing into their document
    assert (
        api.put(f"/notes/annotations/{mark_id}/", body(mine)).status_code == 404
    )  # their id, my document: never a hint
    assert remove(api, mark_id, base_rev=1).status_code == 404
    assert api.post(f"/notes/annotations/{mark_id}/restore/").status_code == 404
    assert api.post(f"/notes/annotations/{mark_id}/card/", {"client_id": str(uuid.uuid4())}).status_code == 404
    batch = api.post("/notes/annotations/batch/", {"document_id": str(doc.id), "ops": []})
    assert batch.status_code == 404
    mixed = api.post(
        "/notes/annotations/batch/",
        {"document_id": str(mine.id), "ops": [{"op": "delete", "id": mark_id, "base_rev": 1}]},
    )
    assert mixed.status_code == 200 and mixed.json_body["results"][0]["status"] == "rejected"
    assert mixed.json_body["results"][0]["error"]["code"] == "not_found"
    stored = Annotation.objects.get(pk=mark_id)
    assert stored.deleted_at is None and stored.rev == 1 and str(stored.user_id) == str(OTHER)
    assert api.get(f"/notes/documents/{uuid.uuid4()}/annotations/").status_code == 404
    assert api.put(f"/notes/annotations/{uuid.uuid4()}/", body(Document(id=uuid.uuid4()))).status_code == 404


def test_every_route_needs_a_token(client):
    mark_id, doc_id = uuid.uuid4(), uuid.uuid4()
    calls = [
        ("get", f"/api/v1/notes/documents/{doc_id}/annotations/"),
        ("put", f"/api/v1/notes/annotations/{mark_id}/"),
        ("delete", f"/api/v1/notes/annotations/{mark_id}/"),
        ("post", f"/api/v1/notes/annotations/{mark_id}/restore/"),
        ("post", "/api/v1/notes/annotations/batch/"),
        ("post", f"/api/v1/notes/annotations/{mark_id}/card/"),
    ]
    for method, path in calls:
        assert getattr(client, method)(path).status_code == 401, (method, path)


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


def test_every_mark_route_is_closed_with_the_notes_pdf_flag_off(api, pdf_flag_off):
    mark_id, doc_id = uuid.uuid4(), uuid.uuid4()
    calls = [
        ("get", f"/notes/documents/{doc_id}/annotations/"),
        ("put", f"/notes/annotations/{mark_id}/"),
        ("delete", f"/notes/annotations/{mark_id}/"),
        ("post", f"/notes/annotations/{mark_id}/restore/"),
        ("post", "/notes/annotations/batch/"),
        ("post", f"/notes/annotations/{mark_id}/card/"),
    ]
    for method, path in calls:
        res = api._send(method, path, {} if method != "get" else None)
        assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled", (method, path)
    assert api.get("/notes/settings/").status_code == 200  # settings stay open
