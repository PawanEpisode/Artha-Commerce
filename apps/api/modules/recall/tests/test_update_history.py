"""R2-W4 C: her history of updates and what changed in a card (`subscriptions/{id}/history/`, `cards/{id}/changes/`)."""

from __future__ import annotations

import pytest

from modules.recall.models import RecallSubscriptionUpdate
from modules.recall.services import erasure
from modules.recall.services import sync as sync_service

from .w22 import ME, card_of, deck_with_student, edit, pointer, publish_next, really_review, unique

pytestmark = pytest.mark.django_db


def history(api, sub):
    res = api.get(f"/recall/subscriptions/{sub.id}/history/")
    assert res.status_code == 200, res.json_body
    return res.json_body["items"]


def test_a_new_subscription_has_no_history(api):
    _, _, sub = deck_with_student(2)
    assert history(api, sub) == []


def test_pressing_apply_records_a_manual_update_with_its_counts_and_changelog(api):
    deck, items, sub = deck_with_student(3)
    really_review(card_of(items[0]))
    edit(items[0], pointer(unique("Rewritten")), "substantive")
    publish_next(deck, changelog="Section 17 reworded.")
    assert api.post(f"/recall/subscriptions/{sub.id}/apply-update/").status_code == 200
    (row,) = history(api, sub)
    assert (row["from_version_no"], row["to_version_no"], row["trigger"]) == (1, 2, "manual")
    assert row["changelog_md"] == "Section 17 reworded." and row["applied_at"].endswith("Z")
    assert row["counts"]["rechecked"] == 1 and row["counts"]["cards_reset"] == 1 and "v" not in row["counts"]


def test_a_replayed_apply_adds_no_second_row(api):
    deck, items, sub = deck_with_student(2)
    edit(items[0], pointer(unique("Typo")), "typo")
    publish_next(deck)
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    assert RecallSubscriptionUpdate.objects.filter(subscription=sub).count() == 1


def test_a_follower_synced_by_the_job_is_recorded_as_automatic(api):
    deck, items, sub = deck_with_student(2)
    edit(items[0], pointer(unique("Typo")), "typo")
    version = publish_next(deck)
    sync_service.sync_subscription(ME, sub.id, target_version_id=version.id)
    assert [r["trigger"] for r in history(api, sub)] == ["auto"]


def test_skipped_versions_are_counted_and_the_newest_update_comes_first(api):
    deck, items, sub = deck_with_student(2)
    edit(items[0], pointer(unique("One")), "typo")
    publish_next(deck)
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    edit(items[0], pointer(unique("Two")), "typo")
    publish_next(deck)
    edit(items[0], pointer(unique("Three")), "typo")
    publish_next(deck)
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    rows = history(api, sub)
    assert [(r["from_version_no"], r["to_version_no"]) for r in rows] == [(2, 4), (1, 2)]
    assert rows[0]["versions_skipped"] == 1


def test_another_students_history_is_a_404(api, other_api):
    _, _, sub = deck_with_student(2)
    assert other_api.get(f"/recall/subscriptions/{sub.id}/history/").status_code == 404


def test_the_history_is_exported_and_erased_with_her_data(api):
    deck, items, sub = deck_with_student(2)
    edit(items[0], pointer(unique("Typo")), "typo")
    publish_next(deck)
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    exported = erasure.export_for_user(ME)
    assert [r["to_no"] for r in exported["subscription_updates"]] == [2]
    assert "summary" in exported["subscription_updates"][0]
    report = erasure.delete_all_for_user(ME)
    assert report["subscription_updates"] == 1 and not RecallSubscriptionUpdate.objects.filter(user_id=ME).exists()


# ---------------------------------------------------------------------------------------------------- one card
def changes(api, card):
    res = api.get(f"/recall/cards/{card.id}/changes/")
    assert res.status_code == 200, res.json_body
    return res.json_body


def test_a_platform_card_lists_its_versions_newest_first_with_what_she_has(api):
    deck, items, sub = deck_with_student(2)
    first = card_of(items[0])
    edit(items[0], pointer(unique("Reworded rule"), "Better answer"), "substantive")
    publish_next(deck)
    before = changes(api, first)
    assert before["platform"] is True and before["waiting"] == 1
    assert [(v["version_no"], v["received"], v["current"]) for v in before["versions"]] == [
        (2, False, False),
        (1, True, True),
    ]
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    after = changes(api, first)
    assert after["waiting"] == 0 and [(v["version_no"], v["current"]) for v in after["versions"]] == [
        (2, True),
        (1, False),
    ]
    assert after["versions"][0]["change_kind"] == "substantive" and "Reworded rule" in after["versions"][0]["text"]


def test_a_content_reset_is_listed_with_its_reason(api):
    deck, items, sub = deck_with_student(2)
    first = really_review(card_of(items[0]))
    edit(items[0], pointer(unique("Rewritten")), "substantive")
    publish_next(deck)
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    body = changes(api, first)
    assert [r["reason"] for r in body["resets"]] == ["substantive"] and body["resets"][0]["at"].endswith("Z")


def test_her_own_card_shows_her_edits(api):
    from .support import made

    card = made(api)
    api.patch(
        f"/recall/cards/{card['id']}/",
        {"base_rev": card["rev"], "fields": {"prompt_md": "New prompt?", "answer_md": "New."}},
    )
    body = api.get(f"/recall/cards/{card['id']}/changes/").json_body
    assert body["platform"] is False and body["waiting"] == 0
    assert [v["version_no"] for v in body["versions"]] == [2, 1] and body["versions"][1]["change_kind"] == "create"


def test_another_students_card_is_a_404(api, other_api):
    _, items, _ = deck_with_student(2)
    assert other_api.get(f"/recall/cards/{card_of(items[0]).id}/changes/").status_code == 404


def test_the_card_read_is_a_fixed_number_of_queries(api, django_assert_max_num_queries):
    deck, items, sub = deck_with_student(2)
    first = card_of(items[0])
    for _ in range(6):
        edit(items[0], pointer(unique("Again")), "typo")
        publish_next(deck)
    with django_assert_max_num_queries(12):
        assert api.get(f"/recall/cards/{first.id}/changes/").status_code == 200
