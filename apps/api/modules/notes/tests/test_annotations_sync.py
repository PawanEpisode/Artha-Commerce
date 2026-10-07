"""Two devices, one mark (ERD 3.6): field-level compare-and-set, comment merge, edit versus delete, batches, range re-links."""

import time
import uuid

import pytest

from modules.notes import selectors
from modules.notes.models import Annotation
from modules.notes.services import document_ranges, links

from .marks_support import OTHER, QUADS, USER, body, create, delta, edit, new_document, remove

pytestmark = pytest.mark.django_db

MOVED = {"quads": [[0.4, 0.4, 0.3, 0.02]]}
ELSEWHERE = {"quads": [[0.6, 0.6, 0.2, 0.02]]}


def _two_devices(api, doc, **fields):
    """The same mark as two devices see it (both at rev 1)."""
    mark = create(api, doc, **fields)
    return mark, dict(mark)


def test_different_fields_on_two_devices_union(api):
    doc = new_document()
    a, b = _two_devices(api, doc)
    assert edit(api, a, color="g", base={"color": "y"}).status_code == 200
    res = edit(api, b, page=2, base={"page": 1})  # stale rev, but it only touches the page
    assert res.status_code == 200 and res.json_body["overwritten"] == [] and res.json_body["merged"] is False
    final = res.json_body["annotation"]
    assert (final["color"], final["page"], final["rev"]) == ("g", 2, 3)


def test_the_same_scalar_is_last_write_wins_and_reported(api):
    doc = new_document()
    a, b = _two_devices(api, doc)
    edit(api, a, color="g", base={"color": "y"})
    res = edit(api, b, color="b", base={"color": "y"})
    assert res.status_code == 200 and res.json_body["overwritten"] == ["color"]
    assert res.json_body["annotation"]["color"] == "b"
    # two devices that agree are not an overwrite
    c, d = _two_devices(api, doc)
    edit(api, c, color="p", base={"color": "y"})
    same = edit(api, d, color="p", base={"color": "y"})
    assert same.json_body["overwritten"] == [] and same.json_body["annotation"]["rev"] == 2


def test_geometry_is_last_write_wins(api):
    doc = new_document()
    a, b = _two_devices(api, doc)
    edit(api, a, geometry=MOVED, base={"geometry": QUADS})
    res = edit(api, b, geometry=ELSEWHERE, base={"geometry": QUADS})
    assert res.status_code == 200 and res.json_body["overwritten"] == ["geometry"]
    assert res.json_body["annotation"]["geometry"] == ELSEWHERE


def test_a_clean_comment_merge_is_flagged_and_keeps_both_edits(api):
    doc = new_document()
    text = "Alpha is first.\n\nMiddle part stays.\n\nOmega is last."
    a, b = _two_devices(api, doc, comment=text)
    edit(api, a, comment=text.replace("Alpha", "ALPHA"), base={"comment": text})
    res = edit(api, b, comment=text.replace("Omega", "OMEGA"), base={"comment": text})
    assert res.status_code == 200 and res.json_body["merged"] is True
    assert res.json_body["annotation"]["comment"] == "ALPHA is first.\n\nMiddle part stays.\n\nOMEGA is last."


@pytest.fixture
def overlapping(api):
    doc = new_document()
    a, b = _two_devices(api, doc, comment="the credit is blocked")
    assert edit(api, a, comment="the credit is allowed", base={"comment": "the credit is blocked"}).status_code == 200
    first = edit(api, b, comment="the credit is reversed", base={"comment": "the credit is blocked"})
    return doc, b, first


def test_an_overlapping_comment_is_409_with_both_sides_and_writes_nothing(api, overlapping):
    doc, b, res = overlapping
    assert res.status_code == 409 and res.json_body["error"]["code"] == "annotation_conflict"
    d = res.json_body["error"]["details"]
    assert d["theirs"]["comment"] == "the credit is allowed" and d["theirs"]["rev"] == 2
    assert d["mine"]["comment"] == "the credit is reversed"
    assert d["theirs_updated_at"] == d["theirs"]["updated_at"] and "device_label" in d
    assert Annotation.objects.get(pk=b["id"]).rev == 2


@pytest.mark.parametrize(
    ("resolution", "expected"),
    [
        ("mine", "the credit is reversed"),
        ("theirs", "the credit is allowed"),
        ("both", "the credit is allowed\n\n---\n\nthe credit is reversed"),
    ],
)
def test_each_resolution_resolves_a_parked_conflict(api, overlapping, resolution, expected):
    _, b, res = overlapping
    theirs = res.json_body["error"]["details"]["theirs"]
    resend = api.put(
        f"/notes/annotations/{b['id']}/",
        {
            "document_id": b["document_id"],
            "base_rev": theirs["rev"],
            "comment": "the credit is reversed",
            "resolution": resolution,
        },
    )
    assert resend.status_code == 200, resend.json_body
    assert resend.json_body["annotation"]["comment"] == expected


def test_edit_beats_delete_both_ways(api):
    doc = new_document()
    a, b = _two_devices(api, doc)
    edit(api, a, color="g", base={"color": "y"})  # rev 2
    kept = remove(api, b["id"], base_rev=1)  # the other device deletes from a stale view
    assert kept.status_code == 200 and kept.json_body["edit_wins"] is True
    assert kept.json_body["annotation"]["deleted_at"] is None and kept.json_body["annotation"]["rev"] == 2
    doc.refresh_from_db()
    assert doc.marks_count == 1

    c, d = _two_devices(api, doc)
    assert remove(api, c["id"], base_rev=1).json_body["annotation"]["deleted_at"]
    doc.refresh_from_db()
    assert doc.marks_count == 1  # only the first mark is live
    revived = edit(api, d, color="b", base={"color": "y"})  # edit from a device that never saw the delete
    assert revived.status_code == 200 and revived.json_body["restored"] is True
    assert revived.json_body["annotation"]["deleted_at"] is None and revived.json_body["annotation"]["color"] == "b"
    doc.refresh_from_db()
    assert doc.marks_count == 2 and Annotation.objects.get(pk=c["id"]).purge_after is None


def test_a_batch_runs_in_order_and_a_failed_op_never_aborts_the_rest(api, other_api):
    doc = new_document()
    foreign = create(other_api, new_document(OTHER))
    kept = create(api, doc)
    ids = [str(uuid.uuid4()) for _ in range(3)]
    ops = [
        {"op": "upsert", **body(doc), "id": ids[0]},
        {"op": "upsert", **body(doc), "id": ids[1], "geometry": {"quads": []}},  # invalid geometry
        {"op": "upsert", **body(doc), "id": foreign["id"]},  # someone else's id
        {"op": "upsert", "id": "not-a-uuid"},  # malformed
        {"op": "upsert", **body(doc), "id": ids[2], "base_rev": 5},  # an edit of a mark that does not exist
        {"op": "delete", "id": kept["id"], "base_rev": 1},
        {"op": "restore", "id": kept["id"]},
        {"op": "nope", "id": str(uuid.uuid4())},
        {"op": "upsert", "id": ids[0], "base_rev": 1, "color": "g"},  # edits what op 1 created, in the same batch
    ]
    res = api.post("/notes/annotations/batch/", {"document_id": str(doc.id), "ops": ops})
    assert res.status_code == 200
    statuses = [r["status"] for r in res.json_body["results"]]
    assert statuses == ["ok", "rejected", "rejected", "rejected", "rejected", "ok", "ok", "rejected", "ok"]
    codes = [r.get("error", {}).get("code") for r in res.json_body["results"]]
    assert (
        codes[1:5] == ["invalid_geometry", "not_found", "validation_error", "not_found"]
        and codes[7] == "validation_error"
    )
    last = res.json_body["results"][-1]["annotation"]
    assert last["color"] == "g" and last["rev"] == 2
    assert res.json_body["results"][6]["restored"] is True
    # failed ops burned no seq: kept (1), created (2), delete (3), restore (4), edit (5): gap free
    assert res.json_body["change_seq"] == 5
    assert sorted(Annotation.objects.filter(document=doc).values_list("seq", flat=True)) == [4, 5]
    doc.refresh_from_db()
    assert (doc.change_seq, doc.marks_count) == (5, 2)


def test_a_batch_conflict_is_a_result_with_both_sides(api, overlapping):
    doc, b, _ = overlapping
    res = api.post(
        "/notes/annotations/batch/",
        {
            "document_id": b["document_id"],
            "ops": [
                {
                    "op": "upsert",
                    "id": b["id"],
                    "base_rev": 1,
                    "comment": "the credit is reversed",
                    "base": {"comment": "the credit is blocked"},
                }
            ],
        },
    )
    r = res.json_body["results"][0]
    assert r["status"] == "conflict" and r["error"]["code"] == "annotation_conflict"
    assert r["error"]["details"]["theirs"]["comment"] == "the credit is allowed"


def test_a_hundred_ops_in_one_batch_are_fast_and_a_hundred_and_one_is_413(api):
    doc = new_document()
    ops = [{"op": "upsert", **body(doc, comment=f"mark {i}"), "id": str(uuid.uuid4())} for i in range(100)]
    started = time.monotonic()
    res = api.post("/notes/annotations/batch/", {"document_id": str(doc.id), "ops": ops})
    elapsed = time.monotonic() - started
    assert res.status_code == 200 and [r["status"] for r in res.json_body["results"]] == ["ok"] * 100
    assert [r["id"] for r in res.json_body["results"]] == [o["id"] for o in ops]  # the client's order
    assert res.json_body["change_seq"] == 100 and elapsed < 5, elapsed
    doc.refresh_from_db()
    assert doc.marks_count == 100
    assert sorted(a["seq"] for a in delta(api, doc)["items"]) == list(range(1, 101))
    big = api.post("/notes/annotations/batch/", {"document_id": str(doc.id), "ops": ops + ops[:1]})
    assert big.status_code == 413 and big.json_body["error"]["code"] == "batch_too_large"
    assert Annotation.objects.count() == 100


def test_a_batch_that_runs_into_the_marks_limit_rejects_only_the_overflow(api):
    from modules.notes.models import QuotaPlan

    QuotaPlan.objects.filter(plan_code="free").update(max_marks_per_document=3)
    doc = new_document()
    ops = [{"op": "upsert", **body(doc), "id": str(uuid.uuid4())} for _ in range(5)]
    res = api.post("/notes/annotations/batch/", {"document_id": str(doc.id), "ops": ops})
    assert [r["status"] for r in res.json_body["results"]] == ["ok"] * 3 + ["rejected"] * 2
    assert res.json_body["results"][3]["error"]["code"] == "quota_exceeded"
    assert res.json_body["marks"] == {"count": 3, "limit": 3, "near_limit": True} and res.json_body["change_seq"] == 3


def test_range_changes_relink_inherited_marks_and_the_delta_feed_carries_them(api, scheme):
    from modules.syllabus.models import Chapter

    gst, heads = Chapter.objects.get(key="gst-itc"), Chapter.objects.get(key="heads-of-income")
    doc = new_document(page_count=20, **links.link_columns(heads.id))
    on_page_2 = create(api, doc, page=2)
    on_page_9 = create(api, doc, page=9)
    explicit = create(api, doc, page=2, chapter_id=str(gst.id))
    assert [m["chapter_source"] for m in (on_page_2, on_page_9, explicit)] == ["document", "document", "explicit"]

    ranges = [{"page_from": 1, "page_to": 5, "chapter_id": gst.id}]
    document_ranges.set_page_ranges(USER, doc.id, ranges)
    before = delta(api, doc)["change_seq"]
    now = {a["id"]: a for a in delta(api, doc)["items"]}
    assert (now[on_page_2["id"]]["chapter_source"], now[on_page_2["id"]]["link"]["chapter_key"]) == ("range", "gst-itc")
    assert now[on_page_9["id"]]["link"]["chapter_key"] == "heads-of-income"  # outside the range: the document default
    assert now[explicit["id"]]["chapter_source"] == "explicit"
    assert (
        now[on_page_2["id"]]["seq"] > on_page_2["seq"] and before == now[on_page_2["id"]]["seq"]
    )  # a device resyncing sees it

    # a new mark on a page inside the range inherits it on create
    fresh = create(api, doc, page=3)
    assert fresh["chapter_source"] == "range" and fresh["link"]["chapter_key"] == "gst-itc"
    # moving an inherited mark out of the range re-derives its chapter; an explicit mark stays put
    moved = edit(api, fresh, page=8, base={"page": 3}).json_body["annotation"]
    assert (moved["chapter_source"], moved["link"]["chapter_key"]) == ("document", "heads-of-income")
    document_ranges.set_page_ranges(USER, doc.id, [])
    assert Annotation.objects.get(pk=on_page_2["id"]).chapter_source == "document"
    assert Annotation.objects.get(pk=explicit["id"]).chapter_source == "explicit"
    assert selectors.delta_annotations(USER, doc.id, since_seq=before).items  # and the clear was fed as well
