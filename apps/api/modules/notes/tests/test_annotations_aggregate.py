"""Highlights and documents in the aggregated view, the counts and the chapter overview (ERD Q-2, Q-3, 5)."""

import uuid
from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from modules.notes.domain.quota import IST
from modules.notes.models import Annotation, Document, ItemTag, Note
from modules.notes.services import document_ranges, links
from modules.syllabus.models import Chapter
from modules.syllabus.tests.helpers import switch_scheme

from .conftest import new_note
from .marks_support import USER, create, new_document, remove

pytestmark = pytest.mark.django_db


def _agg(api, level_id, query="", subject="taxation"):
    return api.get(f"/notes/aggregate/?level={level_id}&subject={subject}{query}").json_body


def _walk(api, level_id, query="", limit=4):
    """Every page of an aggregate listing, as `(type, id)` in order."""
    seen, cursor = [], None
    for _ in range(40):
        url = f"/notes/aggregate/?level={level_id}&subject=taxation&limit={limit}{query}" + (
            f"&cursor={cursor}" if cursor else ""
        )
        page = api.get(url).json_body
        seen += [(i["type"], i["id"]) for i in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            return seen
    raise AssertionError("paging never ended")


BASE = datetime(2026, 3, 10, 12, 0, tzinfo=IST)  # noon in India: the day filter is read in India time


def _stamp(model, pk, minutes):
    """Moves a row to a fixed time (`updated_at` is automatic), so orderings and ties are exact."""
    model.objects.filter(pk=pk).update(updated_at=BASE + timedelta(minutes=minutes))


@pytest.fixture
def library(api, scheme):
    """Notes, marks and documents in one chapter, with fixed times, ties across the three legs, a tag and two colours."""
    gst = Chapter.objects.get(key="gst-itc")
    cols = links.link_columns(gst.id)
    doc = new_document(title="ITC handbook", **cols)
    other_doc = new_document(title="Loose scan")  # unfiled
    tag = api.post("/notes/tags/", {"name": "exam"}).json_body
    notes = [new_note(api, f"note {i}", chapter_id=str(gst.id)) for i in range(3)]
    marks = [
        create(api, doc, comment="yellow one", color="y", quote_exact="blocked credit"),
        create(api, doc, kind="underline", color="g", tag_ids=[tag["id"]]),
        create(api, doc, kind="area", color="y"),
        create(api, doc, kind="sticky", color="b", comment="remember"),
        create(api, doc, kind="textbox", color=None, comment="typed"),
        create(
            api,
            doc,
            kind="ink",
            color="i1",
            geometry={"strokes": [{"pts": [[0.1, 0.1], [0.2, 0.2]], "w": 0.004}], "bbox": [0.1, 0.1, 0.1, 0.1]},
        ),
        create(api, doc, kind="bookmark", color=None),
    ]
    ItemTag.objects.create(user_id=USER, tag_id=tag["id"], note_id=notes[0]["id"])
    ItemTag.objects.create(user_id=USER, tag_id=tag["id"], document=doc)
    # times in minutes: ties between a note, a mark and the document at t=50
    for n, t in zip(notes, (10, 50, 30), strict=True):
        _stamp(Note, n["id"], t)
    for m, t in zip(marks, (50, 20, 40, 50, 60, 70, 80), strict=True):
        _stamp(Annotation, m["id"], t)
    _stamp(Document, doc.id, 50)
    _stamp(Document, other_doc.id, 5)
    return {"doc": doc, "other_doc": other_doc, "notes": notes, "marks": marks, "tag": tag, "gst": gst}


def test_the_all_tab_merges_notes_highlights_and_documents_in_one_order(api, level_id, library):
    items = _agg(api, level_id)["items"]
    kinds = {i["type"] for i in items}
    assert kinds == {"note", "highlight", "document"}
    listed_marks = {i["id"] for i in items if i["type"] == "highlight"}
    ids = [m["id"] for m in library["marks"]]
    assert listed_marks == set(ids[:5])  # ink and bookmark are counted, not listed
    stamps = [i["updated_at"] for i in items]
    assert stamps == sorted(stamps, reverse=True)
    # four rows share one timestamp: ties break by leg (note, highlight, document), then id
    at_50 = [i for i in items if datetime.fromisoformat(i["updated_at"]) == BASE + timedelta(minutes=50)]
    assert [i["type"] for i in at_50] == ["note", "highlight", "highlight", "document"]
    assert [i["id"] for i in at_50[1:3]] == sorted(i["id"] for i in at_50[1:3])
    doc_row = next(i for i in items if i["type"] == "document")
    assert doc_row["id"] == str(library["doc"].id) and doc_row["title"] == "ITC handbook" and "marks_count" in doc_row
    mark_row = next(i for i in items if i["type"] == "highlight")
    assert {"geometry", "quote_exact", "color", "document_id", "chapter_source", "seq"} <= set(mark_row)
    assert str(library["other_doc"].id) not in {i["id"] for i in items}  # filed under no chapter: not in this subject


def test_every_tab_returns_its_own_data(api, level_id, library):
    notes = _agg(api, level_id, "&tab=notes")["items"]
    marks = _agg(api, level_id, "&tab=highlights")["items"]
    docs = _agg(api, level_id, "&tab=documents")["items"]
    assert {i["type"] for i in notes} == {"note"} and len(notes) == 3
    assert {i["type"] for i in marks} == {"highlight"} and len(marks) == 5
    assert {i["type"] for i in docs} == {"document"} and [d["id"] for d in docs] == [str(library["doc"].id)]


def test_paging_never_skips_or_repeats_across_the_three_legs_with_ties(api, level_id, library):
    whole = [(i["type"], i["id"]) for i in _agg(api, level_id, "&limit=100")["items"]]
    assert len(whole) == 3 + 5 + 1
    for limit in (1, 2, 3, 4):
        assert _walk(api, level_id, limit=limit) == whole, limit


def test_filters_apply_to_each_leg_and_paging_stays_correct(api, level_id, library):
    tag = library["tag"]["id"]
    tagged = _walk(api, level_id, f"&tag={tag}", limit=1)
    assert {t for t, _ in tagged} == {"note", "highlight", "document"} and len(
        tagged
    ) == 3  # one of each carries the tag
    # colour and document are mark filters: notes and documents step aside
    yellow = _walk(api, level_id, "&color=y", limit=1)
    assert {t for t, _ in yellow} == {"highlight"} and len(yellow) == 2  # the quote highlight and the area
    ids = [m["id"] for m in library["marks"]]
    assert {i for _, i in yellow} == {ids[0], ids[2]}
    in_doc = _walk(api, level_id, f"&doc={library['doc'].id}", limit=2)
    assert len(in_doc) == 5 and {t for t, _ in in_doc} == {"highlight"}
    assert _walk(api, level_id, f"&doc={uuid.uuid4()}") == []
    assert api.get(f"/notes/aggregate/?level={level_id}&subject=taxation&color=zz").status_code == 400
    # dates: only the rows stamped inside the day filter
    on_the_day = _walk(api, level_id, "&from=2026-03-10&to=2026-03-10", limit=3)
    assert len(on_the_day) == 9 and on_the_day == _walk(api, level_id, limit=3)
    assert _walk(api, level_id, "&from=2026-03-11") == [] and _walk(api, level_id, "&to=2026-03-09") == []
    # text: marks match on their quote and comment, notes on their body, documents on their title
    assert [t for t, _ in _walk(api, level_id, "&q=blocked")] == ["highlight"]
    assert [t for t, _ in _walk(api, level_id, "&q=handbook")] == ["document"]
    # unfiled lists the loose document
    unfiled = api.get("/notes/aggregate/?unfiled=1").json_body["items"]
    assert [i["id"] for i in unfiled if i["type"] == "document"] == [str(library["other_doc"].id)]


def test_deleted_marks_and_marks_of_trashed_documents_leave_every_list(api, level_id, library):
    remove(api, library["marks"][0]["id"], base_rev=1)
    assert library["marks"][0]["id"] not in {i["id"] for i in _agg(api, level_id, "&tab=highlights")["items"]}
    Document.objects.filter(pk=library["doc"].pk).update(deleted_at=timezone.now())
    assert (
        _agg(api, level_id, "&tab=highlights")["items"] == [] and _agg(api, level_id, "&tab=documents")["items"] == []
    )
    counts = api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation").json_body
    row = next(r for r in counts["chapters"] if r["chapter_key"] == "gst-itc")
    assert (row["highlights"], row["marks"], row["documents"]) == (0, 0, 0)


def test_counts_count_highlights_marks_and_documents_once(api, level_id, library):
    res = api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation")
    row = next(r for r in res.json_body["chapters"] if r["chapter_key"] == "gst-itc")
    # highlight, underline, area (3) are highlights; every live mark (7) is a mark; one document
    assert (row["notes"], row["highlights"], row["marks"], row["documents"]) == (3, 3, 7, 1)
    assert row["last_noted_at"] is not None
    assert datetime.fromisoformat(row["last_noted_at"]) == BASE + timedelta(minutes=80)  # the newest mark, any kind
    assert res.json_body["unfiled"] == 1  # the loose document
    # a page range that maps the same chapter must not count the document twice
    document_ranges.set_page_ranges(
        USER, library["doc"].id, [{"page_from": 1, "page_to": 4, "chapter_id": library["gst"].id}]
    )
    again = api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation")
    assert next(r for r in again.json_body["chapters"] if r["chapter_key"] == "gst-itc")["documents"] == 1
    # ETag: a new mark changes it, an unchanged read does not
    etag = res["ETag"]
    assert (
        api.c.get(
            f"/api/v1/notes/aggregate/counts/?level={level_id}&subject=taxation", HTTP_IF_NONE_MATCH=again["ETag"]
        ).status_code
        == 304
    )
    create(api, library["doc"], kind="underline")
    assert api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation")["ETag"] not in (etag, again["ETag"])


def test_a_document_belongs_to_every_chapter_its_ranges_reach(api, level_id, scheme):
    gst, heads = Chapter.objects.get(key="gst-itc"), Chapter.objects.get(key="heads-of-income")
    doc = new_document(page_count=30)
    document_ranges.set_page_ranges(
        USER,
        doc.id,
        [
            {"page_from": 1, "page_to": 9, "chapter_id": gst.id},
            {"page_from": 10, "page_to": 20, "chapter_id": heads.id},
        ],
    )
    mark = create(api, doc, page=12)
    assert mark["chapter_source"] == "range" and mark["link"]["chapter_key"] == "heads-of-income"
    counts = {
        r["chapter_key"]: r
        for r in api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation").json_body["chapters"]
    }
    assert counts["gst-itc"]["documents"] == 1 and counts["heads-of-income"]["documents"] == 1
    assert (counts["gst-itc"]["marks"], counts["heads-of-income"]["marks"]) == (0, 1)
    for key in ("gst-itc", "heads-of-income"):
        docs = _agg(api, level_id, f"&chapter={key}&tab=documents")["items"]
        assert [d["id"] for d in docs] == [str(doc.id)]
    assert _agg(api, level_id, "&chapter=residential-status&tab=documents")["items"] == []
    assert api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation").json_body["unfiled"] == 0


def test_marks_that_inherit_from_ranges_follow_a_scheme_switch(api, level_id, scheme):
    gst, residential = Chapter.objects.get(key="gst-itc"), Chapter.objects.get(key="residential-status")
    doc = new_document(page_count=30)
    document_ranges.set_page_ranges(
        USER,
        doc.id,
        [
            {"page_from": 1, "page_to": 9, "chapter_id": gst.id},
            {"page_from": 10, "page_to": 20, "chapter_id": residential.id},
        ],
    )
    kept, dropped = create(api, doc, page=3), create(api, doc, page=14)
    assert (kept["chapter_source"], dropped["chapter_source"]) == ("range", "range")

    def drop_residential(spec):
        spec["subjects"][0]["chapters"] = [
            c for c in spec["subjects"][0]["chapters"] if c["key"] != "residential-status"
        ]

    new_scheme = switch_scheme(scheme, drop_residential)
    new_gst = Chapter.objects.get(key="gst-itc", subject__scheme=new_scheme)
    counts = api.get(f"/notes/aggregate/counts/?level={level_id}&subject=taxation").json_body
    by_key = {r["chapter_key"]: r for r in counts["chapters"]}
    assert by_key["gst-itc"]["chapter_id"] == str(new_gst.id) and by_key["gst-itc"]["highlights"] == 1
    assert by_key["gst-itc"]["marks"] == 1 and by_key["gst-itc"]["documents"] == 1
    # "Moved or removed" carries the mark and the document that sat under the dropped chapter
    assert counts["moved_or_removed"] == [
        {
            "chapter_key": "residential-status",
            "chapter_name": "Residential status",
            "notes": 0,
            "highlights": 1,
            "marks": 1,
            "documents": 1,
        }
    ]
    listed = _agg(api, level_id, "&chapter=gst-itc&tab=highlights")["items"]
    assert [i["id"] for i in listed] == [kept["id"]] and listed[0]["link"]["chapter_id"] == str(new_gst.id)
    flagged = {a["id"]: a for a in api.get(f"/notes/documents/{doc.id}/annotations/").json_body["items"]}
    assert (
        flagged[dropped["id"]]["link"]["moved_or_removed"] is True
        and flagged[kept["id"]]["link"]["moved_or_removed"] is False
    )


def test_the_chapter_overview_lists_its_documents(api, level_id, library):
    res = api.get(f"/notes/chapters/gst-itc/overview/?level={level_id}&subject=taxation").json_body
    assert res["counts"] == {"notes": 3, "highlights": 3, "marks": 7, "documents": 1}
    assert [d["id"] for d in res["documents"]] == [str(library["doc"].id)]
    assert res["documents"][0]["title"] == "ITC handbook" and res["documents"][0]["marks_count"] == 7
    empty = api.get(f"/notes/chapters/heads-of-income/overview/?level={level_id}&subject=taxation").json_body
    assert empty["documents"] == [] and empty["counts"]["marks"] == 0
