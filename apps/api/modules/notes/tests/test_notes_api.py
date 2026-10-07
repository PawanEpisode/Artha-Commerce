"""Notes over HTTP: auth, create, read, edit with merge and conflict, versions, trash, ownership, validation."""

import uuid

import pytest

from modules.notes.models import Note, NoteVersion, QuotaUsage

from .conftest import age_versions, edit, new_note

pytestmark = pytest.mark.django_db


def test_every_notes_endpoint_needs_a_token(client):
    for path in (
        "/notes/notes/",
        "/notes/tags/",
        "/notes/settings/",
        "/notes/usage/",
        "/notes/aggregate/",
        "/notes/export/",
    ):
        assert client.get(f"/api/v1{path}").status_code == 401, path
    assert client.delete("/api/v1/notes/").status_code == 401


def test_create_then_read_back(api, chapter):
    n = new_note(api, "## Heading\n\nSome **text** about GST", title="GST", chapter_id=str(chapter.id))
    assert n["rev"] == 1 and n["kind"] == "note" and n["title"] == "GST"
    assert n["link"]["chapter_key"] == "gst-itc" and n["link"]["moved_or_removed"] is False
    got = api.get(f"/notes/notes/{n['id']}/").json_body
    assert got["body_md"].startswith("## Heading")
    listed = api.get("/notes/notes/").json_body
    assert [i["id"] for i in listed["items"]] == [n["id"]] and "body_md" not in listed["items"][0]


def test_create_is_idempotent_on_client_id(api):
    cid = str(uuid.uuid4())
    a = api.post("/notes/notes/", {"client_id": cid, "body_md": "one"})
    b = api.post("/notes/notes/", {"client_id": cid, "body_md": "one"})
    assert (a.status_code, b.status_code) == (201, 200)
    assert a.json_body["id"] == b.json_body["id"]
    assert Note.objects.count() == 1 and QuotaUsage.objects.get().notes_active == 1


def test_validation_errors_are_400(api):
    assert api.post("/notes/notes/", {"body_md": "no client id"}).status_code == 400
    assert api.post("/notes/notes/", {"client_id": "nope"}).status_code == 400
    assert api.get("/notes/notes/?limit=0").status_code == 400
    assert api.get("/notes/notes/?subject=taxation").status_code == 400  # needs a level
    assert api.get("/notes/notes/?cursor=%25%25").status_code in (400,)


def test_a_body_that_breaks_the_note_profile_is_422(api):
    res = api.post("/notes/notes/", {"client_id": str(uuid.uuid4()), "body_md": "# A top level heading"})
    assert res.status_code == 422
    body = res.json_body["error"]
    assert body["code"] == "invalid_body" and body["details"]["errors"][0]["code"] == "heading_level"


def test_unknown_chapter_is_422(api, scheme):
    res = api.post("/notes/notes/", {"client_id": str(uuid.uuid4()), "chapter_id": str(uuid.uuid4())})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_chapter"


def test_edit_bumps_the_revision_and_replays_are_harmless(api):
    n = new_note(api, "first")
    res = edit(api, n, body_md="second")
    assert res.status_code == 200 and res.json_body["rev"] == 2 and res.json_body["body_md"] == "second"
    replay = edit(api, n, body_md="second")  # same base_rev, same content: the winning write replayed
    assert replay.status_code == 200 and replay.json_body["rev"] == 2


def test_non_overlapping_edits_from_two_devices_merge(api):
    n = new_note(api, "alpha line\n\nbeta line\n\ngamma line")
    edit(api, n, body_md="alpha line\n\nbeta line\n\ngamma CHANGED")
    res = api.patch(
        f"/notes/notes/{n['id']}/",
        {"base_rev": 1, "base_body_md": n["body_md"], "body_md": "alpha EDITED\n\nbeta line\n\ngamma line"},
    )
    assert res.status_code == 200 and res.json_body["merged"] is True
    assert res.json_body["body_md"] == "alpha EDITED\n\nbeta line\n\ngamma CHANGED"


def test_overlapping_edits_answer_409_with_theirs_mine_and_merged(api):
    n = new_note(api, "the quick brown fox")
    edit(api, n, body_md="the quick red fox")
    res = api.patch(
        f"/notes/notes/{n['id']}/",
        {"base_rev": 1, "base_body_md": n["body_md"], "body_md": "the quick green fox"},
    )
    assert res.status_code == 409 and res.json_body["error"]["code"] == "note_conflict"
    details = res.json_body["error"]["details"]
    assert details["theirs"]["body_md"] == "the quick red fox" and "mine" in details
    assert Note.objects.get().body_md == "the quick red fox"  # nothing written


@pytest.mark.parametrize("resolution,expected", [("mine", "mine text"), ("theirs", "theirs text")])
def test_resolving_a_conflict(api, resolution, expected):
    n = new_note(api, "base text")
    current = edit(api, n, body_md="theirs text").json_body
    res = api.patch(
        f"/notes/notes/{n['id']}/",
        {"base_rev": current["rev"], "body_md": "mine text", "resolution": resolution},
    )
    assert res.status_code == 200 and res.json_body["body_md"] == expected


def test_resolution_both_keeps_everything(api):
    n = new_note(api, "base")
    current = edit(api, n, body_md="theirs").json_body
    res = api.patch(f"/notes/notes/{n['id']}/", {"base_rev": current["rev"], "body_md": "mine", "resolution": "both"})
    assert res.status_code == 200
    assert "theirs" in res.json_body["body_md"] and "mine" in res.json_body["body_md"]


def test_a_resolution_against_a_stale_revision_is_a_new_conflict(api):
    n = new_note(api, "base")
    edit(api, n, body_md="one")
    res = api.patch(f"/notes/notes/{n['id']}/", {"base_rev": 1, "body_md": "mine", "resolution": "mine"})
    assert res.status_code == 409


def test_scalar_fields_last_write_wins_and_report_the_overwrite(api):
    n = new_note(api, "x", title="A")
    edit(api, n, title="B")
    res = api.patch(f"/notes/notes/{n['id']}/", {"base_rev": 1, "base": {"title": "A"}, "title": "C"})
    assert res.status_code == 200 and res.json_body["title"] == "C" and res.json_body["overwritten"] == ["title"]


def test_pin_and_move_and_tags(api, scheme):
    from modules.syllabus.models import Chapter

    n = new_note(api, "x")
    chapter = Chapter.objects.get(key="residential-status")
    tag = api.post("/notes/tags/", {"name": "revise"}).json_body
    res = edit(api, n, pinned=True, chapter_id=str(chapter.id), tag_ids=[tag["id"]])
    body = res.json_body
    assert body["pinned"] and body["link"]["chapter_key"] == "residential-status"
    assert [t["id"] for t in body["tags"]] == [tag["id"]]
    assert api.get("/notes/notes/?unfiled=true").json_body["items"] == []


def test_versions_are_listed_read_and_restored(api, clock):
    n = new_note(api, "v1")
    clock.advance(minutes=30)
    n2 = edit(api, n, body_md="v2").json_body
    clock.advance(minutes=30)
    edit(api, n2, body_md="v3", source="manual")
    rows = api.get(f"/notes/notes/{n['id']}/versions/").json_body["items"]
    assert [r["rev"] for r in rows][:1] == [3] and len(rows) == 3
    assert api.get(f"/notes/notes/{n['id']}/versions/1/").json_body["body_md"] == "v1"
    restored = api.post(f"/notes/notes/{n['id']}/versions/1/restore/").json_body
    assert restored["body_md"] == "v1" and restored["rev"] == 4
    assert api.get(f"/notes/notes/{n['id']}/versions/99/").status_code == 404


def test_autosaves_in_a_burst_coalesce_into_one_version(api, clock):
    n = new_note(api, "a")  # the creation version is a manual one
    cur = n
    for i in range(5):
        cur = edit(api, cur, body_md=f"a{i}").json_body
    assert cur["rev"] == 6
    rows = list(NoteVersion.objects.filter(note_id=n["id"]).order_by("rev"))
    assert [(v.rev, v.body_md) for v in rows] == [(1, "a"), (6, "a4")]


def test_a_pause_starts_a_new_version(api, clock):
    n = new_note(api, "a")
    cur = edit(api, n, body_md="b").json_body
    age_versions(n["id"], seconds=120)
    edit(api, cur, body_md="c")
    assert NoteVersion.objects.filter(note_id=n["id"]).count() == 3


def test_a_long_burst_is_closed_at_the_span_cap(api, clock):
    n = new_note(api, "a")
    cur = edit(api, n, body_md="b").json_body
    age_versions(n["id"], seconds=55)
    cur = edit(api, cur, body_md="c").json_body  # inside the window: folded
    assert NoteVersion.objects.filter(note_id=n["id"]).count() == 2
    from datetime import timedelta

    # the burst has run 11 minutes (kept alive by autosaves under a minute apart): the next autosave opens a new row
    NoteVersion.objects.filter(note_id=n["id"], rev=cur["rev"]).update(created_at=clock.now - timedelta(minutes=11))
    edit(api, cur, body_md="d")
    assert NoteVersion.objects.filter(note_id=n["id"]).count() == 3


def test_a_manual_save_never_coalesces(api, clock):
    n = new_note(api, "a")
    clock.advance(seconds=5)
    edit(api, n, body_md="b", source="manual")
    assert NoteVersion.objects.filter(note_id=n["id"]).count() == 2


def test_trash_restore_and_edit_restores(api, clock):
    n = new_note(api, "keep me")
    res = api.delete(f"/notes/notes/{n['id']}/")
    assert res.status_code == 200 and res.json_body["purge_after"]
    assert api.get("/notes/notes/").json_body["items"] == []
    assert [i["id"] for i in api.get("/notes/notes/?trashed=true").json_body["items"]] == [n["id"]]
    assert QuotaUsage.objects.get().notes_active == 0
    back = api.post(f"/notes/notes/{n['id']}/restore/").json_body
    assert back["deleted_at"] is None and QuotaUsage.objects.get().notes_active == 1
    api.delete(f"/notes/notes/{n['id']}/")
    cur = api.get(f"/notes/notes/{n['id']}/").json_body
    res = edit(api, cur, body_md="edited in the trash")
    assert res.json_body["restored"] is True and res.json_body["deleted_at"] is None


def test_trashing_twice_is_harmless(api):
    n = new_note(api, "x")
    assert api.delete(f"/notes/notes/{n['id']}/").status_code == 200
    assert api.delete(f"/notes/notes/{n['id']}/").status_code == 200
    assert QuotaUsage.objects.get().notes_active == 0


def test_other_students_notes_are_404(api, other_api):
    n = new_note(api, "mine")
    nid = n["id"]
    assert other_api.get(f"/notes/notes/{nid}/").status_code == 404
    assert other_api.patch(f"/notes/notes/{nid}/", {"base_rev": 1, "body_md": "x"}).status_code == 404
    assert other_api.delete(f"/notes/notes/{nid}/").status_code == 404
    assert other_api.post(f"/notes/notes/{nid}/restore/").status_code == 404
    assert other_api.get(f"/notes/notes/{nid}/versions/").status_code == 404
    assert other_api.get(f"/notes/notes/{nid}/versions/1/").status_code == 404
    assert other_api.post(f"/notes/notes/{nid}/versions/1/restore/").status_code == 404
    assert other_api.get("/notes/notes/").json_body["items"] == []
    assert other_api.put("/notes/items/tags/", {"item_type": "note", "item_id": nid, "tag_ids": []}).status_code == 404


def test_changes_feed_returns_what_moved_since_the_cursor(api):
    a = new_note(api, "a")
    first = api.get("/notes/notes/changes/").json_body
    assert [i["id"] for i in first["items"]] == [a["id"]] and first["has_more"] is False
    b = new_note(api, "b")
    nxt = api.get(f"/notes/notes/changes/?since={first['next_since']}").json_body
    assert [i["id"] for i in nxt["items"]] == [b["id"]]


def test_list_paginates_with_a_cursor(api, clock):
    ids = []
    for i in range(5):
        clock.advance(seconds=1)
        ids.append(new_note(api, f"n{i}")["id"])
    p1 = api.get("/notes/notes/?limit=2").json_body
    p2 = api.get(f"/notes/notes/?limit=2&cursor={p1['next_cursor']}").json_body
    p3 = api.get(f"/notes/notes/?limit=2&cursor={p2['next_cursor']}").json_body
    got = [i["id"] for p in (p1, p2, p3) for i in p["items"]]
    assert got == ids[::-1] and p3["next_cursor"] is None
