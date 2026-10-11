"""R2-W2 endpoints: update preview, apply, follow or pin (FR-F15-47, FR-F15-48)."""

from __future__ import annotations

import pytest

from core import jobs as core_jobs
from core.models import Job
from modules.recall import jobs as recall_jobs
from modules.recall import subscribers
from modules.recall.models import RecallCard
from modules.recall.services import sync as sync_service

from .w22 import ME, card_of, deck_with_student, edit, pointer, publish_next, really_review, unique

pytestmark = pytest.mark.django_db


def url(sub, action=""):
    return f"/recall/subscriptions/{sub.id}/{action}"


def substantive(items, i=0):
    return edit(items[i], pointer(unique("Rewritten")), "substantive")


def test_preview_is_read_only_and_counts_by_kind(api):
    deck, items, sub = deck_with_student(3)
    really_review(card_of(items[0]))
    substantive(items)
    edit(items[1], pointer(unique("Typo")), "typo")
    publish_next(deck, changelog="Fixes.")
    before = list(RecallCard.objects.filter(user_id=ME).values_list("id", "rev"))
    res = api.get(url(sub, "update/"))
    assert res.status_code == 200
    body = res.json_body
    assert body["update_available"] is True and body["from_version_no"] == 1 and body["to_version_no"] == 2
    assert body["counts"]["substantive"] == 1
    assert body["changelog_md"] == "Fixes."
    assert body["returning_today"] >= 1
    assert list(RecallCard.objects.filter(user_id=ME).values_list("id", "rev")) == before  # nothing written
    sub.refresh_from_db()
    assert sub.synced_version.version_no == 1


def test_preview_with_nothing_new_says_so(api):
    _, _, sub = deck_with_student(2)
    body = api.get(url(sub, "update/")).json_body
    assert body["update_available"] is False and body["to_version_no"] == body["from_version_no"]


def test_apply_syncs_and_is_idempotent(api):
    deck, items, sub = deck_with_student(3)
    really_review(card_of(items[0]))
    substantive(items)
    publish_next(deck)
    first = api.post(url(sub, "apply-update/"))
    assert first.status_code == 200, first.json_body
    assert first.json_body["result"]["changed"] is True and first.json_body["result"]["cards_reset"] == 1
    assert first.json_body["deck"]["subscription"]["update_available"] is False
    snap = list(RecallCard.objects.filter(user_id=ME).values_list("id", "rev"))
    second = api.post(url(sub, "apply-update/"))
    assert second.status_code == 200 and second.json_body["result"]["changed"] is False
    assert list(RecallCard.objects.filter(user_id=ME).values_list("id", "rev")) == snap


def test_another_students_subscription_is_a_404(api, other_api):
    deck, _, sub = deck_with_student(2)
    assert other_api.get(url(sub, "update/")).status_code == 404
    assert other_api.post(url(sub, "apply-update/")).status_code == 404
    assert other_api.patch(url(sub), {"follow_updates": False}).status_code == 404


def test_apply_has_its_own_throttle(api, settings):
    from rest_framework.settings import api_settings  # noqa: F401

    deck, _, sub = deck_with_student(2)
    codes = [api.post(url(sub, "apply-update/")).status_code for _ in range(32)]
    assert codes[:30] == [200] * 30 and 429 in codes[30:]


def test_pin_then_follow_queues_a_job_and_pin_only_records_the_pending_version(api):
    deck, items, sub = deck_with_student(3)
    assert api.patch(url(sub), {"follow_updates": False}).json_body["deck"]["subscription"]["follow_updates"] is False
    substantive(items)
    version = publish_next(deck)
    subscribers.on_deck_published(deck_version_id=version.id)
    core_jobs.run_pending(types=recall_jobs.LIGHT_TYPES, budget_seconds=20, worker="t")
    sub.refresh_from_db()
    assert sub.synced_version.version_no == 1 and sub.pending_version_id == version.id  # a pin is never moved
    sub_json = api.get(f"/recall/decks/{deck.id}/").json_body["deck"]["subscription"]
    assert sub_json["update_available"] is True and sub_json["follow_updates"] is False
    res = api.patch(url(sub), {"follow_updates": True})
    assert res.status_code == 200
    assert Job.objects.filter(type=sync_service.JOB_SYNC_SUBSCRIPTION).count() == 1
    api.patch(url(sub), {"follow_updates": True})  # again: still one job
    assert Job.objects.filter(type=sync_service.JOB_SYNC_SUBSCRIPTION).count() == 1
    recall_jobs.tick()
    sub.refresh_from_db()
    assert sub.synced_version_id == version.id


def test_follow_patch_validates_the_body(api):
    _, _, sub = deck_with_student(2)
    assert api.patch(url(sub), {}).status_code == 400
    assert api.patch(url(sub), {"follow_updates": "maybe"}).status_code == 400
