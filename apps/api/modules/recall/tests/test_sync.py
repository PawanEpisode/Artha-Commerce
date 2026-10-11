"""R2-W2 sync: a subscription moves from the deck version she has to a newer one (FR-F15-47, FR-F15-48)."""

from __future__ import annotations

import pytest
from django.utils import timezone

from modules.coverage.tests.conftest import USER as ME
from modules.recall.domain import limits as lim
from modules.recall.models import RecallCard, RecallReviewLog, RecallScheduleEvent, RecallSettings
from modules.recall.services import reviews
from modules.recall.services import sync as sync_service

from .w22 import (
    card_of,
    cards_of,
    deck_with_student,
    edit,
    lv,
    new_platform_item,
    pointer,
    publish_next,
    really_review,
    study,
    unique,
)

pytestmark = pytest.mark.django_db


def run(sub, **kw):
    return sync_service.sync_subscription(ME, sub.id, **kw)


def snapshot():
    return sorted(RecallCard.objects.filter(user_id=ME).values_list("id", "rev", "status", "item_version_id"))


def test_a_typo_and_a_clarify_swap_the_version_silently():
    deck, items, sub = deck_with_student(3)
    study()
    before = {c.item_id: c for c in RecallCard.objects.filter(user_id=ME)}
    edit(items[0], pointer(unique("Typo fixed")), "typo")
    edit(items[1], pointer(unique("Clearer words")), "clarify")
    publish_next(deck)
    result = run(sub)
    assert result.changed and result.silent == 2 and result.rechecked == 0 and result.cards_reset == 0
    for item in items[:2]:
        now, old = card_of(item), before[item.id]
        assert now.item_version_id == lv(item) and now.item_version_id != old.item_version_id
        assert now.rev == old.rev + 1 and not now.needs_recheck
        assert (now.stability, now.due_at, now.state, now.reps) == (old.stability, old.due_at, old.state, old.reps)
    assert card_of(items[2]).rev == before[items[2].id].rev
    assert not RecallScheduleEvent.objects.filter(kind="content_reset").exists()


@pytest.mark.parametrize(
    ("kind", "reason", "event_reason"),
    [("substantive", "content_changed", "substantive"), ("amendment", "amendment", "amendment")],
)
def test_a_substantive_or_amendment_change_returns_the_card_for_recheck_today(kind, reason, event_reason):
    deck, items, sub = deck_with_student(2)
    study()
    edit(items[0], pointer(unique("New rule")), kind)
    publish_next(deck)
    before = card_of(items[0])
    log_before = RecallReviewLog.objects.filter(user_id=ME).count()
    result = run(sub)
    card = card_of(items[0])
    assert result.rechecked == 1 and result.cards_reset == 1
    assert card.needs_recheck and card.recheck_reason == reason
    assert card.item_version_id == lv(items[0])
    assert card.stability == lim.CONTENT_RESET_STABILITY_CAP_DAYS
    assert card.state == before.state and card.reps == before.reps and card.due_at <= timezone.now()
    events = list(RecallScheduleEvent.objects.filter(card=card))
    assert [(e.kind, e.reason_code) for e in events] == [("content_reset", event_reason)]
    assert events[0].stability_before == 20.0 and events[0].stability_after == lim.CONTENT_RESET_STABILITY_CAP_DAYS
    assert RecallReviewLog.objects.filter(user_id=ME).count() == log_before
    assert not card_of(items[1]).needs_recheck  # the other card is untouched


def test_replaying_a_reset_card_gives_the_stored_card():
    deck, items, sub = deck_with_student(1)
    really_review(card_of(items[0]))
    assert card_of(items[0]).stability > lim.CONTENT_RESET_STABILITY_CAP_DAYS
    edit(items[0], pointer(unique("Rewritten")), "substantive")
    publish_next(deck)
    run(sub)
    stored = card_of(items[0])
    assert reviews.replay_card(ME, stored.id) is False  # nothing to rewrite: the row already equals the fold
    again = card_of(items[0])
    cols = (
        "state",
        "step",
        "stability",
        "difficulty",
        "due_scheduled_at",
        "postponed_until",
        "due_at",
        "reps",
        "lapses",
    )
    assert [getattr(again, c) for c in cols] == [getattr(stored, c) for c in cols] and again.rev == stored.rev


def test_the_worst_change_across_skipped_versions_applies():
    deck, items, sub = deck_with_student(3)
    study()
    edit(items[0], pointer(unique("v2 typo")), "typo")
    edit(items[1], pointer(unique("v2 clarify")), "clarify")
    publish_next(deck)
    edit(items[0], pointer(unique("v3 substantive")), "substantive")  # typo then substantive: substantive wins
    publish_next(deck)
    result = run(sub)
    assert result.versions_skipped == 1 and result.rechecked == 1 and result.silent == 1
    assert card_of(items[0]).needs_recheck and not card_of(items[1]).needs_recheck
    assert card_of(items[1]).item_version_id == lv(items[1])


def test_added_items_create_cards_at_or_above_her_floor_and_reuse_her_archived_card():
    deck, items, sub = deck_with_student(2)
    sub.min_importance = "important"
    sub.save(update_fields=["min_importance"])
    low = new_platform_item("Low", importance="bullet")
    high = new_platform_item("High", importance="mandatory")
    cloze = new_platform_item(
        "Cloze", importance="important", kind="cloze", fields={"text_md": "{{c1::a}} and {{c2::b}}"}
    )
    publish_next(deck, added=[low, high, cloze])
    result = run(sub)
    assert (
        result.added == 2 and result.cards_created == 3
    )  # high, and the two faces of the cloze; low is below her floor
    assert not RecallCard.objects.filter(user_id=ME, item=low).exists()
    assert [c.ordinal for c in cards_of(cloze)] == [1, 2] and len(cards_of(high)) == 1
    # an item she archived earlier comes back with its progress
    gone = new_platform_item("Gone", importance="mandatory")
    publish_next(deck, added=[gone])
    run(sub)
    study(item=gone)
    RecallCard.objects.filter(user_id=ME, item=gone).update(status="archived")
    publish_next(deck, removed=[gone])
    run(sub)
    publish_next(deck, added=[gone])
    result = run(sub)
    back = card_of(gone)
    assert result.cards_restored == 1 and back.status == "active" and back.reps == 3 and back.subscription_id == sub.id


def test_a_removed_item_archives_her_card_but_keeps_its_progress():
    deck, items, sub = deck_with_student(3)
    study()
    publish_next(deck, removed=[items[2]])
    result = run(sub)
    gone = card_of(items[2])
    assert result.removed == 1 and result.cards_archived == 1
    assert gone.status == "archived" and gone.reps == 3 and gone.stability == 20.0


def test_a_removed_item_stays_when_another_active_subscription_still_holds_it():
    from modules.recall.services import decks as deck_service
    from modules.recall.services import subscriptions

    from .w11 import draft_deck

    deck, items, sub = deck_with_student(2)
    other, draft = draft_deck([items[1]], title="Second deck")
    deck_service.publish_deck_version(
        deck_service.EDITOR if hasattr(deck_service, "EDITOR") else __import__("uuid").uuid4(), other.id, draft.id
    )
    other_sub = subscriptions.subscribe(ME, other.id).subscription
    publish_next(deck, removed=[items[1]])
    run(sub)
    kept = card_of(items[1])
    assert kept.status == "active" and kept.subscription_id == other_sub.id


def test_cloze_faces_follow_the_new_version():
    deck, _, sub = deck_with_student(1)
    cloze = new_platform_item(
        "Cloze", importance="mandatory", kind="cloze", fields={"text_md": "{{c1::a}} {{c2::b}} {{c3::c}}"}
    )
    publish_next(deck, added=[cloze])
    run(sub)
    assert [c.ordinal for c in cards_of(cloze)] == [1, 2, 3]
    study(item=cloze)
    edit(cloze, {"text_md": "{{c1::a}} {{c2::b}} {{c3::c}} {{c4::d}}"}, "substantive")
    publish_next(deck)
    run(sub)
    assert [c.ordinal for c in cards_of(cloze)] == [1, 2, 3, 4]
    edit(cloze, {"text_md": "{{c1::a}} {{c2::b}}"}, "clarify")
    publish_next(deck)
    run(sub)
    live = {c.ordinal for c in cards_of(cloze) if c.status == "active"}
    assert live == {1, 2} and {c.ordinal for c in cards_of(cloze) if c.status == "archived"} == {3, 4}


def test_a_second_run_with_the_same_target_changes_nothing():
    deck, items, sub = deck_with_student(3)
    study()
    edit(items[0], pointer(unique("Rewritten")), "substantive")
    edit(items[1], pointer(unique("Typo")), "typo")
    publish_next(deck, added=[new_platform_item("Added", importance="mandatory")])
    first = run(sub)
    assert first.changed
    rows, events = snapshot(), RecallScheduleEvent.objects.count()
    second = run(sub)
    assert second.changed is False
    assert snapshot() == rows and RecallScheduleEvent.objects.count() == events


def test_the_run_sets_the_synced_version_and_clears_pending():
    deck, items, sub = deck_with_student(2)
    version = publish_next(deck, added=[new_platform_item("Added")])
    sub.pending_version = version
    sub.save(update_fields=["pending_version"])
    run(sub)
    sub.refresh_from_db()
    assert sub.synced_version_id == version.id == sub.pinned_version_id
    assert sub.pending_version_id is None and sub.last_sync_at is not None


def test_a_reviewed_card_during_a_vacation_waits_for_the_day_after_and_replays_the_same():
    deck, items, sub = deck_with_student(1)
    really_review(card_of(items[0]))
    settings = RecallSettings.objects.get_or_create(user_id=ME)[0]
    settings.vacation_until = timezone.localdate() + timezone.timedelta(days=3)
    settings.save()
    edit(items[0], pointer(unique("Rewritten")), "substantive")
    publish_next(deck)
    run(sub)
    card = card_of(items[0])
    assert card.needs_recheck and card.postponed_until is not None and card.due_at == card.postponed_until
    kinds = sorted(RecallScheduleEvent.objects.filter(card=card).values_list("kind", flat=True))
    assert kinds == ["content_reset", "postpone"]
    assert reviews.replay_card(ME, card.id) is False


def test_a_card_never_reviewed_only_swaps_its_version():
    deck, items, sub = deck_with_student(1)
    edit(items[0], pointer(unique("Rewritten")), "substantive")
    publish_next(deck)
    result = run(sub)
    card = card_of(items[0])
    assert result.cards_reset == 0 and not card.needs_recheck and card.state == 0
    assert card.item_version_id == lv(items[0]) and not RecallScheduleEvent.objects.exists()


def test_a_pinned_or_archived_subscription_is_not_touched_by_a_follow_sync_but_apply_works_on_active():
    deck, items, sub = deck_with_student(2)
    publish_next(deck, added=[new_platform_item("Added", importance="mandatory")])
    sub.status = "archived"
    sub.save(update_fields=["status"])
    assert run(sub).changed is False


def test_another_students_subscription_is_not_found():
    from rest_framework.exceptions import NotFound

    from .factories import OTHER

    _, _, sub = deck_with_student(1)
    with pytest.raises(NotFound):
        sync_service.sync_subscription(OTHER, sub.id)
