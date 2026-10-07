"""Page ranges of a document: replace-the-set, overlaps, and the marks that inherit their chapter from a range."""

import uuid

import pytest
from django.db import connection

from modules.notes.domain import chapter_inheritance
from modules.notes.models import Annotation, DocumentChapter
from modules.syllabus.models import Chapter, Topic

from .factories import ALICE, make_annotation, make_document

pytestmark = pytest.mark.django_db


def chap(key):
    return str(Chapter.objects.get(key=key).id)


def put(api, document, ranges):
    return api.put(f"/notes/documents/{document.id}/chapters/", {"ranges": ranges})


def marks_by_page(document):
    return {m.page: (m.chapter_key, m.chapter_source) for m in Annotation.objects.filter(document=document)}


def test_the_set_is_replaced_and_comes_back_with_names(api, scheme, fake_storage):
    document = make_document(ALICE, page_count=50)
    res = put(
        api,
        document,
        [
            {"page_from": 10, "page_to": 20, "chapter_id": chap("residential-status")},
            {"page_from": 1, "page_to": 9, "chapter_id": chap("gst-itc"), "source": "outline"},
        ],
    )
    assert res.status_code == 200 and res.json_body["relinked"] == 0
    first, second = res.json_body["ranges"]
    assert (first["page_from"], first["page_to"], first["chapter_key"], first["source"]) == (1, 9, "gst-itc", "outline")
    assert (
        first["subject_key"] == "taxation"
        and first["chapter_name"]
        and first["subject_name"]
        and first["topic_id"] is None
    )
    assert (second["page_from"], second["chapter_key"], second["source"]) == (10, "residential-status", "user")
    replaced = put(api, document, [{"page_from": 5, "page_to": 6, "chapter_id": chap("gst-itc")}]).json_body["ranges"]
    assert len(replaced) == 1 and DocumentChapter.objects.filter(document=document).count() == 1
    assert api.get(f"/notes/documents/{document.id}/").json_body["ranges"][0]["page_from"] == 5
    assert put(api, document, []).json_body["ranges"] == [] and not DocumentChapter.objects.exists()


def test_a_range_may_name_a_topic_of_its_chapter(api, scheme, fake_storage, ids):
    document = make_document(ALICE, page_count=50)
    topic = str(Topic.objects.create(chapter_id=ids["gst"], key="rcm", name="Reverse charge").id)
    res = put(api, document, [{"page_from": 1, "page_to": 4, "chapter_id": ids["gst"], "topic_id": topic}])
    assert res.json_body["ranges"][0]["topic_id"] == topic and res.json_body["ranges"][0]["topic_name"]
    wrong = put(api, document, [{"page_from": 1, "page_to": 4, "chapter_id": ids["residential"], "topic_id": topic}])
    assert wrong.status_code == 422 and wrong.json_body["error"]["code"] == "unknown_chapter"


def test_overlapping_ranges_are_409_and_change_nothing(api, scheme, fake_storage):
    document = make_document(ALICE, page_count=50)
    put(api, document, [{"page_from": 1, "page_to": 3, "chapter_id": chap("gst-itc")}])
    res = put(
        api,
        document,
        [
            {"page_from": 1, "page_to": 10, "chapter_id": chap("gst-itc")},
            {"page_from": 10, "page_to": 12, "chapter_id": chap("residential-status")},
        ],
    )
    assert res.status_code == 409 and res.json_body["error"]["code"] == "ranges_overlap"
    assert [(r.page_from, r.page_to) for r in DocumentChapter.objects.all()] == [(1, 3)]


@pytest.mark.skipif(connection.vendor != "postgresql", reason="the exclusion constraint is PostgreSQL DDL")
def test_the_database_constraint_is_the_last_word_on_overlaps(api, scheme, fake_storage, monkeypatch):
    monkeypatch.setattr(
        chapter_inheritance, "validate_ranges", lambda ranges: None
    )  # as if two writers raced past the check
    document = make_document(ALICE, page_count=50)
    res = put(
        api,
        document,
        [
            {"page_from": 1, "page_to": 10, "chapter_id": chap("gst-itc")},
            {"page_from": 5, "page_to": 12, "chapter_id": chap("residential-status")},
        ],
    )
    assert res.status_code == 409 and res.json_body["error"]["code"] == "ranges_overlap"
    assert not DocumentChapter.objects.exists()


@pytest.mark.parametrize(
    "ranges",
    [
        [{"page_from": 5, "page_to": 4}],
        [{"page_from": 0, "page_to": 4}],
        [{"page_from": 40, "page_to": 60}],  # past the last page
    ],
)
def test_invalid_ranges_are_refused(api, scheme, fake_storage, ranges):
    document = make_document(ALICE, page_count=50)
    ranges = [{**r, "chapter_id": chap("gst-itc")} for r in ranges]
    res = put(api, document, ranges)
    assert res.status_code in (400, 422)
    if res.status_code == 422:
        assert res.json_body["error"]["code"] == "invalid_range"
    assert not DocumentChapter.objects.exists()


def test_ranges_need_a_known_chapter_and_a_list(api, scheme, fake_storage):
    document = make_document(ALICE, page_count=50)
    unknown = put(api, document, [{"page_from": 1, "page_to": 2, "chapter_id": str(uuid.uuid4())}])
    assert unknown.status_code == 422 and unknown.json_body["error"]["code"] == "unknown_chapter"
    assert put(api, document, [{"page_from": 1, "page_to": 2}]).status_code == 400
    assert api.put(f"/notes/documents/{document.id}/chapters/", {}).status_code == 400


def test_existing_marks_follow_the_ranges_but_explicit_links_are_never_overwritten(api, scheme, fake_storage):
    document = make_document(ALICE, page_count=50)
    from modules.notes.services import links

    explicit = make_annotation(
        document,
        page=3,
        chapter_source="explicit",
        **links.link_columns(chapter_id=Chapter.objects.get(key="companies-act").id),
    )
    for page in (2, 3, 12, 30):
        if page != 3:
            make_annotation(document, page=page)
    res = put(
        api,
        document,
        [
            {"page_from": 1, "page_to": 5, "chapter_id": chap("gst-itc")},
            {"page_from": 10, "page_to": 15, "chapter_id": chap("residential-status")},
        ],
    )
    assert res.json_body["relinked"] == 2  # pages 2 and 12; page 30 has no range and no default; page 3 is explicit
    got = marks_by_page(document)
    assert got[2] == ("gst-itc", "range") and got[12] == ("residential-status", "range") and got[30] == (None, "none")
    assert got[3] == ("companies-act", "explicit")
    assert Annotation.objects.get(pk=explicit.pk).chapter_key == "companies-act"


def test_changing_or_clearing_ranges_relinks_to_the_next_best_source(api, scheme, fake_storage):
    from modules.notes.services import links

    document = make_document(ALICE, page_count=50, **links.link_columns(Chapter.objects.get(key="heads-of-income").id))
    make_annotation(document, page=2)
    make_annotation(document, page=40)
    put(api, document, [{"page_from": 1, "page_to": 5, "chapter_id": chap("gst-itc")}])
    assert marks_by_page(document) == {2: ("gst-itc", "range"), 40: ("heads-of-income", "document")}
    cleared = put(api, document, [])
    assert cleared.json_body["relinked"] == 1
    assert marks_by_page(document) == {2: ("heads-of-income", "document"), 40: ("heads-of-income", "document")}
    same = put(api, document, [])
    assert same.json_body["relinked"] == 0  # idempotent


def test_changing_the_default_chapter_relinks_the_inheriting_marks_only(api, scheme, fake_storage):
    from modules.notes.services import links

    document = make_document(ALICE, page_count=50)
    inheriting = make_annotation(document, page=7)
    own = make_annotation(
        document, page=8, chapter_source="explicit", **links.link_columns(Chapter.objects.get(key="companies-act").id)
    )
    res = api.patch(f"/notes/documents/{document.id}/", {"chapter_id": chap("gst-itc")})
    assert res.status_code == 200
    assert Annotation.objects.get(pk=inheriting.pk).chapter_key == "gst-itc"
    assert Annotation.objects.get(pk=inheriting.pk).chapter_source == "document"
    assert Annotation.objects.get(pk=own.pk).chapter_key == "companies-act"


def test_relinking_announces_the_counts_of_the_chapters_involved(
    api, scheme, fake_storage, django_capture_on_commit_callbacks, capture_events
):
    seen = capture_events("notes_chapter_counts_changed")
    document = make_document(ALICE, page_count=50)
    make_annotation(document, page=2)
    with django_capture_on_commit_callbacks(execute=True):
        put(api, document, [{"page_from": 1, "page_to": 5, "chapter_id": chap("gst-itc")}])
    assert ("gst-itc", "relinked") in [(e["chapter_key"], e["reason"]) for e in seen]
