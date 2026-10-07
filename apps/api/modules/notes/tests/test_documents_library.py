"""The library list, one document, edits with `base_rev`, tags, progress and duplicate detection."""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from modules.coverage.tests.conftest import OTHER
from modules.notes.models import ItemTag
from modules.syllabus.models import Chapter

from .factories import ALICE, BOB, make_attachment, make_content, make_document, make_tag

pytestmark = pytest.mark.django_db


def ids(res):
    return [d["id"] for d in res.json_body["items"]]


def test_the_library_lists_recent_first_never_opened_last_and_hides_other_students(api, fake_storage):
    now = timezone.now()
    old = make_document(ALICE, title="Opened long ago", last_opened_at=now - timedelta(days=5))
    new = make_document(ALICE, title="Opened today", last_opened_at=now)
    never = make_document(ALICE, title="Never opened")
    make_document(BOB, title="Not yours")
    res = api.get("/notes/documents/")
    assert ids(res) == [str(new.id), str(old.id), str(never.id)] and res.json_body["next_cursor"] is None
    row = res.json_body["items"][0]
    assert (
        row["title"] == "Opened today"
        and row["status"] == "ready"
        and row["tags"] == []
        and row["link"]["chapter_id"] is None
    )
    assert api.get("/notes/documents/?sort=title").json_body["items"][0]["title"] == "Never opened"


def test_continue_reading_is_status_ready_limit_three_and_the_list_pages_with_a_cursor(api, fake_storage):
    now = timezone.now()
    for n in range(5):
        make_document(ALICE, title=f"d{n}", last_opened_at=now - timedelta(hours=n))
    make_document(ALICE, status="inspecting")
    assert len(ids(api.get("/notes/documents/?status=ready&limit=3"))) == 3
    first = api.get("/notes/documents/?limit=4").json_body
    second = api.get(f"/notes/documents/?limit=4&cursor={first['next_cursor']}").json_body
    assert len(first["items"]) == 4 and len(second["items"]) == 2 and second["next_cursor"] is None
    assert not {d["id"] for d in first["items"]} & {d["id"] for d in second["items"]}
    assert api.get("/notes/documents/?cursor=@@@").status_code == 400


def test_filters_by_chapter_tag_status_source_search_and_trash(api, fake_storage, scheme):
    gst = Chapter.objects.get(key="gst-itc")
    from modules.notes.services import links

    filed = make_document(ALICE, title="Indirect tax notes", source_kind="coaching", **links.link_columns(gst.id))
    plain = make_document(ALICE, title="Other", status="needs_password")
    tag = make_tag(ALICE, "revise")
    ItemTag.objects.create(user_id=ALICE, tag=tag, document=filed)
    trashed = make_document(
        ALICE, title="Binned", deleted_at=timezone.now(), purge_after=timezone.now() + timedelta(days=30)
    )
    level = str(scheme.level_id)
    assert ids(api.get(f"/notes/documents/?level={level}&subject=taxation&chapter=gst-itc")) == [str(filed.id)]
    assert ids(api.get(f"/notes/documents/?tag={tag.id}")) == [str(filed.id)]
    assert ids(api.get("/notes/documents/?status=needs_password")) == [str(plain.id)]
    assert ids(api.get("/notes/documents/?source=coaching")) == [str(filed.id)]
    assert ids(api.get("/notes/documents/?q=INDIRECT")) == [str(filed.id)]
    assert ids(api.get("/notes/documents/?trashed=1")) == [str(trashed.id)]
    assert str(trashed.id) not in ids(api.get("/notes/documents/"))
    assert api.get("/notes/documents/?sort=sideways").status_code == 400
    assert api.get("/notes/documents/?limit=500").status_code == 400
    assert filed.id and api.get("/notes/documents/").json_body["items"][-1]["tags"] in (
        [],
        [{"id": str(tag.id), "name": "revise", "color_key": None}],
    )


def test_detail_carries_a_signed_url_while_the_file_is_clean_and_openable(api, fake_storage):
    content = make_content(
        page_count=12,
        page_meta=[{"w": 595.0, "h": 842.0}] * 12,
        outline=[{"title": "Intro", "page": 1, "children": []}],
        is_scanned=False,
    )
    doc = make_document(ALICE, content=content, page_count=12)
    body = api.get(f"/notes/documents/{doc.id}/").json_body
    assert body["can_open"] is True and body["file_url"].startswith("https://") and body["file_url_expires_at"]
    assert body["page_meta"][0] == {"w": 595.0, "h": 842.0} and body["outline"][0]["title"] == "Intro"
    assert (
        body["client_id"] is None
        and body["ranges"] == []
        and body["change_seq"] == 0
        and body["has_javascript"] is False
    )
    assert body["is_scanned"] is False and body["text_status"] == "pending" and body["is_encrypted"] is False
    for status in ("reserved", "rejected", "failed", "expired"):
        doc.status = status
        doc.save()
        shown = api.get(f"/notes/documents/{doc.id}/").json_body
        assert shown["file_url"] is None and shown["can_open"] is False, status
    doc.status = "needs_password"
    doc.save()
    assert api.get(f"/notes/documents/{doc.id}/").json_body["file_url"]  # the browser can ask for the password itself


def test_the_file_url_is_never_issued_for_a_file_that_is_not_clean(api, fake_storage):
    doc = make_document(ALICE, attachment=make_attachment(ALICE, status="uploaded"), status="scanning")
    assert api.get(f"/notes/documents/{doc.id}/").json_body["file_url"] is None


def test_a_cover_is_signed_for_one_hour_when_the_thumbnail_is_clean(api, fake_storage):
    cover = make_attachment(ALICE, kind="note_image", mime="image/webp", ext="webp")
    doc = make_document(ALICE, cover_attachment=cover)
    assert api.get(f"/notes/documents/{doc.id}/").json_body["cover_url"].startswith("https://")
    assert api.get("/notes/documents/").json_body["items"][0]["cover_url"].startswith("https://")


def test_patch_edits_metadata_bumps_rev_and_refuses_a_stale_base_rev(api, fake_storage, scheme):
    doc = make_document(ALICE, title="Old")
    gst = Chapter.objects.get(key="gst-itc")
    tag = make_tag(ALICE, "formulas")
    res = api.patch(
        f"/notes/documents/{doc.id}/",
        {
            "base_rev": 1,
            "title": "  New   title ",
            "source_kind": "own_notes",
            "edition_label": "May 2027",
            "chapter_id": str(gst.id),
            "tag_ids": [str(tag.id)],
        },
    )
    assert res.status_code == 200
    got = res.json_body
    assert (got["title"], got["rev"], got["source_kind"], got["edition_label"]) == (
        "New title",
        2,
        "own_notes",
        "May 2027",
    )
    assert got["link"]["chapter_key"] == "gst-itc" and [t["name"] for t in got["tags"]] == ["formulas"]
    stale = api.patch(f"/notes/documents/{doc.id}/", {"base_rev": 1, "title": "Lost update"})
    err = stale.json_body["error"]
    assert stale.status_code == 409 and err["code"] == "document_conflict"
    assert err["details"]["theirs"]["title"] == "New title" and err["details"]["theirs"]["rev"] == 2
    assert api.patch(f"/notes/documents/{doc.id}/", {"title": "No base wins"}).json_body["title"] == "No base wins"
    cleared = api.patch(
        f"/notes/documents/{doc.id}/", {"chapter_id": None, "edition_label": "", "tag_ids": []}
    ).json_body
    assert cleared["link"]["chapter_id"] is None and cleared["edition_label"] is None and cleared["tags"] == []


def test_patch_validation_and_unknown_chapter_or_tag(api, fake_storage, scheme):
    doc = make_document(ALICE)
    url = f"/notes/documents/{doc.id}/"
    assert api.patch(url, {"title": ""}).status_code == 400
    assert api.patch(url, {"title": "x" * 201}).status_code == 400
    assert api.patch(url, {"source_kind": "nope"}).status_code == 400
    assert api.patch(url, {"base_rev": 0}).status_code == 400
    unknown = api.patch(url, {"chapter_id": str(uuid.uuid4())})
    assert unknown.status_code == 422 and unknown.json_body["error"]["code"] == "unknown_chapter"
    foreign_tag = make_tag(BOB, "theirs")
    assert api.patch(url, {"tag_ids": [str(foreign_tag.id)]}).status_code == 422
    assert not ItemTag.objects.exists()


def test_progress_is_last_write_wins_and_clamped_and_stamps_last_opened(api, fake_storage):
    doc = make_document(ALICE, page_count=10)
    url = f"/notes/documents/{doc.id}/progress/"
    res = api.put(url, {"last_page": 4, "last_zoom": "125", "page_tone": "night"})
    assert res.status_code == 200
    assert (res.json_body["last_page"], res.json_body["last_zoom"], res.json_body["page_tone"]) == (4, "125", "night")
    assert res.json_body["last_opened_at"]
    assert (
        api.put(url, {"last_page": 4, "last_zoom": "125", "page_tone": "night"}).json_body["last_page"] == 4
    )  # idempotent
    assert api.put(url, {"last_page": 99, "last_zoom": "fit"}).json_body["last_page"] == 10
    assert api.put(url, {"last_page": 3, "last_zoom": "fit"}).json_body["page_tone"] == "night"  # omitted: unchanged
    assert api.put(url, {"last_page": 3, "last_zoom": "fit", "page_tone": None}).json_body["page_tone"] is None
    for bad in (
        {"last_page": 0, "last_zoom": "fit"},
        {"last_page": 1, "last_zoom": "huge"},
        {"last_page": 1, "last_zoom": "fit", "page_tone": "neon"},
        {},
    ):
        assert api.put(url, bad).status_code == 400
    from modules.notes.models import Document

    assert Document.objects.get(pk=doc.id).rev == 1  # reading position is not a metadata edit


def test_a_second_copy_of_the_same_file_points_at_the_first(api, other_api, fake_storage):
    content = make_content()
    first = make_document(ALICE, content=content, title="First copy")
    second = make_document(ALICE, content=content, title="Second copy")
    unrelated = make_document(ALICE, content=make_content())
    theirs = make_document(OTHER, content=content)
    rows = {d["id"]: d for d in api.get("/notes/documents/").json_body["items"]}
    assert rows[str(first.id)]["duplicate_of"] is None
    assert rows[str(second.id)]["duplicate_of"] == str(first.id)
    assert rows[str(unrelated.id)]["duplicate_of"] is None
    assert api.get(f"/notes/documents/{second.id}/").json_body["duplicate_of"] == str(first.id)
    assert other_api.get(f"/notes/documents/{theirs.id}/").json_body["duplicate_of"] is None  # never another student's
    first.deleted_at = timezone.now()
    first.save()
    assert api.get(f"/notes/documents/{second.id}/").json_body["duplicate_of"] is None  # only LIVE documents count
