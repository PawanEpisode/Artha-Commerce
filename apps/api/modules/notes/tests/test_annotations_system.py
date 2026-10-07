"""Marks under the hood: counts events, the purge job, account erasure, real concurrency, and a random-ops property test."""

import hashlib
import random
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.db import close_old_connections, connection
from django.utils import timezone

from core import events as bus
from modules.media.tests.conftest import FakeStorage
from modules.notes import events, jobs
from modules.notes.models import Annotation, Document, ItemTag
from modules.notes.services import account, annotations, links
from modules.notes.services.annotation_ops import AnnotationOp, apply_annotation_ops

from .marks_support import QUADS, USER, create, edit, new_document, remove


@pytest.fixture
def heard(monkeypatch, django_capture_on_commit_callbacks):
    """Records `notes_chapter_counts_changed` events; the on-commit callbacks run when the test leaves the block."""
    seen = []
    monkeypatch.setattr(bus, "_subscribers", defaultdict(list))
    bus.subscribe(events.NOTES_CHAPTER_COUNTS_CHANGED, lambda **payload: seen.append(payload))

    class Heard:
        def __call__(self):
            return seen

        def capture(self):
            return django_capture_on_commit_callbacks(execute=True)

    return Heard()


@pytest.mark.django_db
def test_counts_events_fire_on_create_trash_restore_and_relink_but_not_on_other_edits(api, scheme, heard):
    from modules.syllabus.models import Chapter

    gst, heads = Chapter.objects.get(key="gst-itc"), Chapter.objects.get(key="heads-of-income")
    doc = new_document(**links.link_columns(gst.id))
    with heard.capture():
        mark = create(api, doc, comment="a")
    assert [(e["reason"], e["chapter_key"]) for e in heard()] == [("created", "gst-itc")]
    assert (
        heard()[0]["counts"]["highlights"] == 1 and heard()[0]["counts"]["marks"] == 1 and "comment" not in heard()[0]
    )

    heard().clear()
    with heard.capture():
        mark = edit(api, mark, comment="b", color="g", base={"comment": "a"}).json_body["annotation"]
        create(
            api,
            doc,
            kind="ink",
            geometry={"strokes": [{"pts": [[0.1, 0.1], [0.2, 0.2]], "w": 0.004}], "bbox": [0.1, 0.1, 0.1, 0.1]},
        )
        create(api, doc, kind="bookmark")
    assert heard() == []  # a plain edit, a pen drawing and a bookmark never announce

    with heard.capture():
        mark = edit(api, mark, chapter_id=str(heads.id), base={"chapter_id": str(gst.id)}).json_body["annotation"]
    assert [e["reason"] for e in heard()] == ["relinked", "relinked"]
    assert {e["chapter_key"] for e in heard()} == {"gst-itc", "heads-of-income"}

    heard().clear()
    with heard.capture():
        remove(api, mark["id"], base_rev=mark["rev"])
    with heard.capture():
        api.post(f"/notes/annotations/{mark['id']}/restore/")
    assert [(e["reason"], e["chapter_key"]) for e in heard()] == [
        ("trashed", "heads-of-income"),
        ("restored", "heads-of-income"),
    ]
    assert heard()[0]["counts"]["highlights"] == 0 and heard()[1]["counts"]["highlights"] == 1


@pytest.mark.django_db
def test_the_purge_job_removes_only_tombstones_past_their_30_days(api):
    doc = new_document()
    old, fresh, live = (create(api, doc) for _ in range(3))
    remove(api, old["id"], base_rev=1)
    remove(api, fresh["id"], base_rev=1)
    Annotation.objects.filter(pk=old["id"]).update(purge_after=timezone.now() - timedelta(days=1))
    assert annotations.purge_expired(limit=1) == 1
    assert set(Annotation.objects.values_list("id", flat=True)) == {uuid.UUID(fresh["id"]), uuid.UUID(live["id"])}
    Annotation.objects.filter(pk=fresh["id"]).update(purge_after=timezone.now() - timedelta(minutes=1))
    assert jobs.purge_job({})["marks"] == 1
    assert Annotation.objects.count() == 1
    doc.refresh_from_db()
    assert doc.marks_count == 1  # tombstones were never counted


@pytest.mark.django_db
def test_delete_all_for_user_removes_marks_and_their_tags(api, other_api):
    doc, theirs = new_document(), new_document(uuid.uuid4())
    tag = api.post("/notes/tags/", {"name": "t"}).json_body
    create(api, doc, tag_ids=[tag["id"]])
    kept = Annotation.objects.create(
        user_id=theirs.user_id, document=theirs, page=1, kind="highlight", geometry=QUADS, seq=1
    )
    report = account.delete_all_for_user(USER)
    assert report["marks"] == 1
    assert not Annotation.objects.filter(user_id=USER).exists() and not ItemTag.objects.filter(user_id=USER).exists()
    assert Annotation.objects.filter(pk=kept.pk).exists()
    assert not Document.objects.filter(user_id=USER).exists()


# --- concurrency (PostgreSQL) ---------------------------------------------------------------------------------------------------
postgres_only = pytest.mark.skipif(connection.vendor != "postgresql", reason="row locks need PostgreSQL")


def _race(fn, n=8):
    def run(i):
        close_old_connections()
        try:
            return fn(i)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(run, range(n)))


@postgres_only
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_eight_concurrent_writers_leave_a_gap_free_change_seq_and_an_exact_counter():
    doc = new_document()

    def writer(i):
        results = []
        for _ in range(5):
            op = AnnotationOp(
                "upsert", uuid.uuid4(), fields={"kind": "highlight", "page": 1, "geometry": QUADS, "color": "y"}
            )
            results.append(apply_annotation_ops(USER, doc.id, [op]))
        return results

    batches = [b for per_thread in _race(writer) for b in per_thread]
    assert all(b.results[0].status == "ok" for b in batches)
    doc.refresh_from_db()
    seqs = sorted(Annotation.objects.filter(document=doc).values_list("seq", flat=True))
    assert seqs == list(range(1, 41))  # distinct and gap free
    assert (
        doc.change_seq == 40
        and doc.marks_count == Annotation.objects.filter(document=doc, deleted_at=None).count() == 40
    )


@postgres_only
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_edits_of_different_fields_of_one_mark_both_land():
    doc = new_document()
    mark_id = uuid.uuid4()
    apply_annotation_ops(
        USER,
        doc.id,
        [AnnotationOp("upsert", mark_id, fields={"kind": "highlight", "page": 1, "geometry": QUADS, "color": "y"})],
    )

    def writer(i):
        fields = {"color": "g"} if i % 2 else {"page": 2}
        base = {"color": "y"} if i % 2 else {"page": 1}
        return apply_annotation_ops(
            USER, doc.id, [AnnotationOp("upsert", mark_id, base_rev=1, base=base, fields=fields)]
        ).results[0]

    results = _race(writer)
    assert {r.status for r in results} == {"ok"}
    row = Annotation.objects.get(pk=mark_id)
    assert (row.color, row.page) == ("g", 2) and row.rev == 3  # two real writes (the repeats were replays)
    assert row.seq == Document.objects.get(pk=doc.pk).change_seq == 3


# --- property: random ops never corrupt the document or its file --------------------------------------------------------------
@pytest.mark.django_db
@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_random_op_sequences_keep_the_counters_exact_and_the_original_file_untouched(seed, monkeypatch):
    fake = FakeStorage()
    monkeypatch.setattr("modules.media.services.get_storage", lambda: fake)
    doc = new_document(page_count=6)
    key = (doc.attachment.bucket, doc.attachment.path)
    original = b"%PDF-1.7 the student's original bytes " + bytes(range(200))
    fake.objects[key] = original
    digest = hashlib.sha256(original).hexdigest()

    rng = random.Random(seed)
    ids = [uuid.uuid4() for _ in range(6)]
    known_rev: dict[uuid.UUID, int] = {}
    for _ in range(120):
        mark_id, kind = rng.choice(ids), rng.choice(["upsert", "upsert", "delete", "restore"])
        rev = known_rev.get(mark_id)
        fields = {}
        if kind == "upsert":
            fields = {
                "color": rng.choice(["y", "g", "b"]),
                "comment": rng.choice(["", "x", "a longer comment"]),
                "page": rng.randint(1, 6),
            }
            if rev is None:
                fields |= {"kind": "highlight", "geometry": QUADS}
        base_rev = None if kind != "upsert" or rev is None else rng.choice([rev, max(rev - 1, 1)])
        batch = apply_annotation_ops(USER, doc.id, [AnnotationOp(kind, mark_id, base_rev=base_rev, fields=fields)])
        result = batch.results[0]
        if result.annotation is not None:
            known_rev[mark_id] = result.annotation.rev
        live = Annotation.objects.filter(document=doc, deleted_at=None).count()
        doc.refresh_from_db()
        assert doc.marks_count == live and 0 <= live <= len(ids)
        seqs = list(Annotation.objects.filter(document=doc).values_list("seq", flat=True))
        assert len(seqs) == len(set(seqs)) and max(seqs, default=0) <= doc.change_seq
    assert (
        hashlib.sha256(fake.objects[key]).hexdigest() == digest and len(fake.objects) == 1
    )  # marks never touch the file
