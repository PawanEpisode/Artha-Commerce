"""The client owns the note id (contract "R1 follow-up"): POST with `id`, idempotent PUT, two devices, id collisions, replay order."""

import uuid

import pytest

from modules.notes.models import Note, QuotaUsage

pytestmark = pytest.mark.django_db


def test_post_with_an_id_uses_it_and_client_id_defaults_to_it(api):
    nid = str(uuid.uuid4())
    res = api.post("/notes/", {"id": nid, "body_md": "mine"})
    assert res.status_code == 201 and res.json_body["id"] == nid
    assert str(Note.objects.get(pk=nid).client_id) == nid


def test_old_clients_with_only_a_client_id_still_get_a_server_id(api):
    cid = str(uuid.uuid4())
    res = api.post("/notes/", {"client_id": cid})
    assert res.status_code == 201 and res.json_body["id"] != cid


def test_a_create_with_neither_id_is_400(api):
    assert api.post("/notes/", {"body_md": "x"}).status_code == 400
    assert api.put(f"/notes/{uuid.uuid4()}/", {"body_md": "x"}).status_code == 201  # the path id is enough


def test_put_creates_then_replays_without_changing_anything(api):
    nid = str(uuid.uuid4())
    first = api.put(f"/notes/{nid}/", {"title": "T", "body_md": "one"})
    again = api.put(f"/notes/{nid}/", {"title": "T", "body_md": "one"})
    third = api.put(f"/notes/{nid}/", {"title": "different", "body_md": "other"})
    assert (first.status_code, again.status_code, third.status_code) == (201, 200, 200)
    assert third.json_body["title"] == "T" and third.json_body["body_md"] == "one"  # a replay never overwrites
    assert Note.objects.count() == 1 and QuotaUsage.objects.get().notes_active == 1


def test_a_replayed_create_never_overwrites_a_later_edit(api):
    nid = str(uuid.uuid4())
    created = api.put(f"/notes/{nid}/", {"body_md": "v1"}).json_body
    api.patch(f"/notes/{nid}/", {"base_rev": created["rev"], "body_md": "v2"})
    replay = api.put(f"/notes/{nid}/", {"body_md": "v1"})
    assert replay.status_code == 200 and replay.json_body["body_md"] == "v2" and replay.json_body["rev"] == 2


def test_two_devices_creating_the_same_id_make_one_note(api):
    nid = str(uuid.uuid4())
    phone = api.put(f"/notes/{nid}/", {"body_md": "from the phone"})
    laptop = api.post("/notes/", {"id": nid, "body_md": "from the laptop"})
    assert (phone.status_code, laptop.status_code) == (201, 200)
    assert laptop.json_body["body_md"] == "from the phone"
    assert Note.objects.count() == 1 and QuotaUsage.objects.get().notes_active == 1


def test_an_id_of_another_student_is_404_and_their_note_is_unchanged(api, other_api):
    nid = str(uuid.uuid4())
    theirs = other_api.put(f"/notes/{nid}/", {"title": "private", "body_md": "secret"})
    assert theirs.status_code == 201
    stored = Note.objects.get(pk=nid)
    for res in (
        api.put(f"/notes/{nid}/", {"title": "mine", "body_md": "taking over"}),
        api.post("/notes/", {"id": nid, "body_md": "taking over"}),
    ):
        assert res.status_code == 404
        assert "private" not in str(res.json_body) and "exists" not in str(res.json_body).lower()
    after = Note.objects.get(pk=nid)
    assert (after.user_id, after.title, after.body_md, after.rev) == (
        stored.user_id,
        stored.title,
        stored.body_md,
        stored.rev,
    )
    assert (
        Note.objects.count() == 1
        and not QuotaUsage.objects.filter(notes_active__gt=0).exclude(pk=stored.user_id).exists()
    )
    assert api.get(f"/notes/{nid}/").status_code == 404  # and it is still invisible to the other student


def test_the_same_answer_for_a_missing_and_a_foreign_id_on_patch(api, other_api):
    nid = str(uuid.uuid4())
    other_api.put(f"/notes/{nid}/", {"body_md": "theirs"})
    foreign = api.patch(f"/notes/{nid}/", {"base_rev": 1, "body_md": "x"})
    missing = api.patch(f"/notes/{uuid.uuid4()}/", {"base_rev": 1, "body_md": "x"})
    assert foreign.status_code == missing.status_code == 404


def test_a_trashed_note_replays_as_it_is(api):
    nid = str(uuid.uuid4())
    api.put(f"/notes/{nid}/", {"body_md": "bye"})
    assert api.delete(f"/notes/{nid}/").status_code == 200
    again = api.put(f"/notes/{nid}/", {"body_md": "bye"})
    assert again.status_code == 200 and again.json_body["deleted_at"] is not None


def test_offline_create_edit_then_replay_in_order(api):
    """A phone created the note, tagged it and edited it offline: PUT, PUT items/tags, PATCH base_rev 1; and the replay is safe."""
    nid = str(uuid.uuid4())
    tag = api.post("/notes/tags/", {"name": "Revise"}).json_body
    queue = [
        ("put", f"/notes/{nid}/", {"title": "Offline", "body_md": "typed on the train"}),
        ("put", "/notes/items/tags/", {"item_type": "note", "item_id": nid, "tag_ids": [tag["id"]]}),
        ("patch", f"/notes/{nid}/", {"base_rev": 1, "body_md": "typed on the train, then edited"}),
    ]
    for _ in range(2):  # the second pass is the "request succeeded but the response was lost" replay
        codes = [getattr(api, method)(path, body).status_code for method, path, body in queue]
        assert codes[0] in (200, 201) and codes[1] == 200 and codes[2] == 200
    note = api.get(f"/notes/{nid}/").json_body
    assert note["body_md"].endswith("then edited") and [t["id"] for t in note["tags"]] == [tag["id"]]
    assert Note.objects.count() == 1
