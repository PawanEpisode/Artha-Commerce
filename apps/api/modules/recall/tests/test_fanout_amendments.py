"""R2-W2: the publish fan-out in chunks, and the amendment port (FR-F15-47, FR-F15-49)."""

from __future__ import annotations

import uuid

import pytest

from core import events
from core import jobs as core_jobs
from core.models import Job
from modules.recall import jobs as recall_jobs
from modules.recall import subscribers
from modules.recall.models import RecallAmendmentFlag, RecallCard, RecallItem, RecallScheduleEvent, RecallSubscription
from modules.recall.services import amendments as amend
from modules.recall.services import subscriptions
from modules.recall.services import sync as sync_service

from .factories import make_card, make_item, reviewed_fields
from .w22 import ME, deck_with_student, edit, pointer, publish_next, study, unique

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _wired():
    events.clear()
    subscribers.register()
    yield
    events.clear()


def drain():
    return core_jobs.run_pending(types=recall_jobs.LIGHT_TYPES, budget_seconds=30, worker="t")


# ------------------------------------------------------------------------------------------- fan-out
def test_the_publish_event_syncs_followers_in_chunks_and_marks_pins(monkeypatch):
    monkeypatch.setattr(sync_service.domain, "SYNC_CHUNK", 2)
    deck, items, sub = deck_with_student(2)
    users = [uuid.uuid4() for _ in range(4)]
    subs = [subscriptions.subscribe(u, deck.id).subscription for u in users]
    pinned = subs[0]
    RecallSubscription.objects.filter(pk=pinned.pk).update(follow_updates=False)
    edit(items[0], pointer(unique("New")), "substantive")
    version = publish_next(deck)
    events.emit("recall_deck_published", deck_version_id=version.id)
    jobs = Job.objects.filter(type=sync_service.JOB_SYNC_SUBSCRIBERS)
    assert jobs.count() == 1
    drain()
    assert jobs.count() >= 3  # 5 active subscriptions in chunks of 2
    keys = list(jobs.values_list("dedupe_key", flat=True))
    assert len(keys) == len(set(keys))
    for s in [sub, *subs]:
        s.refresh_from_db()
    assert all(s.synced_version_id == version.id for s in [sub, *subs[1:]])
    assert pinned.synced_version.version_no == 1 and pinned.pending_version_id == version.id
    assert sync_service.fanout_stats(version.id)["failed"] == 0


def test_the_event_twice_queues_one_job_and_a_rerun_changes_nothing():
    deck, items, _ = deck_with_student(2)
    edit(items[0], pointer(unique("New")), "substantive")
    version = publish_next(deck)
    events.emit("recall_deck_published", deck_version_id=version.id)
    events.emit("recall_deck_published", deck_version_id=version.id)
    assert Job.objects.filter(type=sync_service.JOB_SYNC_SUBSCRIBERS, payload__chunk=0).count() == 1
    drain()
    snap = list(RecallCard.objects.filter(user_id=ME).values_list("id", "rev"))
    assert sync_service.sync_chunk(version.id).followed == 0
    assert list(RecallCard.objects.filter(user_id=ME).values_list("id", "rev")) == snap


def test_one_failing_subscription_never_stops_the_chunk(monkeypatch):
    deck, items, sub = deck_with_student(2)
    subscriptions.subscribe(uuid.uuid4(), deck.id)
    edit(items[0], pointer(unique("New")), "substantive")
    version = publish_next(deck)
    real = sync_service.sync_subscription

    def flaky(user_id, sub_id, **kw):
        if sub_id == sub.id:
            raise RuntimeError("boom")
        return real(user_id, sub_id, **kw)

    monkeypatch.setattr(sync_service, "sync_subscription", flaky)
    out = sync_service.sync_chunk(version.id)
    assert out.failed == 1 and out.followed == 1
    assert Job.objects.filter(type=sync_service.JOB_SYNC_SUBSCRIPTION).count() == 1
    monkeypatch.setattr(sync_service, "sync_subscription", real)
    drain()
    sub.refresh_from_db()
    assert sub.synced_version_id == version.id


def test_a_superseded_version_is_skipped():
    deck, items, _ = deck_with_student(2)
    edit(items[0], pointer(unique("v2")), "substantive")
    v2 = publish_next(deck)
    edit(items[1], pointer(unique("v3")), "substantive")
    publish_next(deck)
    assert sync_service.sync_chunk(v2.id).followed == 0


def test_retry_failed_requeues_only_failed_jobs():
    deck, items, _ = deck_with_student(2)
    edit(items[0], pointer(unique("v2")), "substantive")
    v2 = publish_next(deck)
    events.emit("recall_deck_published", deck_version_id=v2.id)
    Job.objects.update(status=Job.Status.FAILED, attempts=5)
    assert sync_service.fanout_stats(v2.id)["failed"] == 1
    assert sync_service.retry_failed(v2.id) == 1
    assert sync_service.fanout_stats(v2.id) == {"queued": 1, "running": 0, "done": 0, "failed": 0}


# --------------------------------------------------------------------------------------- amendments
def platform_card_with_keys(keys, chapter=None):
    deck, items, _ = deck_with_student(2)
    extra = {"chapter_id": chapter, "subject_key": "taxation", "chapter_key": "gst-itc"} if chapter else {}
    RecallItem.objects.filter(pk=items[0].pk).update(reference_keys=keys, **extra)
    return deck, items


def own_card(keys):
    item = make_item(ME)
    RecallItem.objects.filter(pk=item.pk).update(reference_keys=keys)
    return make_card(item, ME, **reviewed_fields(15.0))


def fire(kind="amendment_published", **extra):
    payload = {
        "amendment_id": str(uuid.uuid4()),
        "revision_id": str(uuid.uuid4()),
        "provision_keys": ["s17(5)"],
        **extra,
    }
    events.emit(kind, **payload)
    return payload


def test_a_published_amendment_flags_matching_items_and_her_own_cards_without_touching_memory():
    deck, items = platform_card_with_keys(["s17(5)"])
    mine = own_card(["s17(5)"])
    untouched = own_card(["s9"])
    before = (mine.stability, mine.due_at, mine.rev)
    n_events = RecallScheduleEvent.objects.count()
    payload = fire()
    drain()
    assert RecallAmendmentFlag.objects.filter(item=items[0], amendment_id=payload["amendment_id"]).count() == 1
    mine.refresh_from_db(), untouched.refresh_from_db()
    assert mine.needs_recheck and mine.recheck_reason == "amendment" and mine.recheck_ref == payload["amendment_id"]
    assert (mine.stability, mine.due_at) == before[:2]  # memory untouched
    assert not untouched.needs_recheck
    assert RecallScheduleEvent.objects.count() == n_events  # no schedule event
    assert RecallCard.objects.get(pk=mine.pk).state == 2


def test_the_same_event_twice_flags_once():
    platform_card_with_keys(["s17(5)"])
    own_card(["s17(5)"])
    payload = fire()
    events.emit("amendment_published", **payload)
    drain()
    drain()
    assert RecallAmendmentFlag.objects.count() == 1
    assert Job.objects.filter(type=amend.JOB_FLAG_AMENDMENT, payload__stage="platform").count() == 1


def test_a_retraction_clears_only_what_that_amendment_set():
    deck, items = platform_card_with_keys(["s17(5)"])
    mine = own_card(["s17(5)"])
    payload = fire()
    drain()
    other = own_card(["s17(5)"])
    RecallCard.objects.filter(pk=other.pk).update(needs_recheck=True, recheck_reason="substantive", recheck_ref="dv:x")
    fire("amendment_retracted", amendment_id=payload["amendment_id"], revision_id=None)
    drain()
    assert RecallAmendmentFlag.objects.count() == 0
    mine.refresh_from_db(), other.refresh_from_db()
    assert not mine.needs_recheck
    assert other.needs_recheck and other.recheck_reason == "substantive"


def test_a_non_material_correction_is_ignored_and_a_material_one_counts():
    platform_card_with_keys(["s17(5)"])
    fire("amendment_corrected", material=False)
    assert Job.objects.filter(type=amend.JOB_FLAG_AMENDMENT).count() == 0
    fire("amendment_corrected", material=True)
    assert Job.objects.filter(type=amend.JOB_FLAG_AMENDMENT).count() == 1


def test_without_provision_keys_the_chapter_decides_for_platform_items(scheme, ids):
    chapter = ids["chapter"] if "chapter" in ids else None
    from modules.syllabus.models import Chapter

    chapter = Chapter.objects.get(key="gst-itc")
    deck, items = platform_card_with_keys([], chapter=chapter.id)
    own = own_card(["s17(5)"])
    payload = {"amendment_id": str(uuid.uuid4()), "revision_id": None, "chapter_ids": [str(chapter.id)]}
    events.emit("amendment_published", **payload)
    drain()
    assert RecallAmendmentFlag.objects.filter(item=items[0]).exists()
    own.refresh_from_db()
    assert not own.needs_recheck  # her own cards need a key


def test_a_bad_payload_queues_nothing():
    events.emit("amendment_published", amendment_id="not-a-uuid")
    assert Job.objects.count() == 0


def test_the_queue_and_card_rows_show_the_chip_and_the_ribbon(api):
    deck, items = platform_card_with_keys(["s17(5)"])
    own_card(["s17(5)"])
    fire()
    drain()
    rows = api.get(f"/recall/decks/{deck.id}/").json_body["items"]
    assert [r["under_review"] for r in rows][:1] == [True]
    study(item=items[0])
    q = api.get("/recall/queue/?source=deck&deck_id=" + str(deck.id))
    assert q.status_code == 200
