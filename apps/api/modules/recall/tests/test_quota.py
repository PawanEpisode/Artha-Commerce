import pytest

from core import plans
from modules.recall.errors import QuotaExceeded
from modules.recall.models import RecallDeck, RecallQuotaPlan, RecallQuotaUsage
from modules.recall.services import quota

from .factories import USER, make_deck, make_item

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _free_plan():
    yield
    plans.register_plan_provider(None)


def usage() -> RecallQuotaUsage:
    return RecallQuotaUsage.objects.get(pk=USER)


def test_limits_come_from_the_plan_row_of_the_students_plan():
    assert quota.limits_for(USER).max_cards == 1500
    plans.register_plan_provider(lambda user_id: "pro")
    assert quota.limits_for(USER).max_cards == 20000
    assert quota.pack_size(USER) == 500


def test_a_missing_plan_row_falls_back_to_free_never_to_unlimited():
    plans.register_plan_provider(lambda user_id: "enterprise")
    assert quota.limits_for(USER).max_cards == 1500


def test_a_plan_row_can_be_changed_without_code():
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=3)
    assert quota.limits_for(USER).max_cards == 3


def test_reserving_cards_counts_up_to_the_limit_and_then_refuses_with_details():
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=3)
    quota.reserve_cards(USER)
    quota.reserve_cards(USER, 2)
    assert usage().cards_active == 3
    with pytest.raises(QuotaExceeded) as caught:
        quota.reserve_cards(USER)
    assert caught.value.extra == {"kind": "cards", "used": 3, "limit": 3, "plan": "free"}
    assert usage().cards_active == 3  # a refusal changes nothing


def test_a_bulk_reservation_is_all_or_nothing():
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=5)
    quota.reserve_cards(USER, 4)
    with pytest.raises(QuotaExceeded):
        quota.reserve_cards(USER, 2)
    assert usage().cards_active == 4


def test_release_gives_back_and_clamps_at_zero():
    quota.reserve_cards(USER, 2)
    quota.release_cards(USER)
    assert usage().cards_active == 1
    quota.release_cards(USER, 10)
    assert usage().cards_active == 0


def test_decks_have_their_own_limit():
    RecallQuotaPlan.objects.filter(pk="free").update(max_decks=1)
    quota.reserve_deck(USER)
    with pytest.raises(QuotaExceeded) as caught:
        quota.reserve_deck(USER)
    assert caught.value.extra["kind"] == "decks"
    quota.release_deck(USER)
    quota.reserve_deck(USER)


def test_cards_per_deck_is_a_conditional_update_on_the_deck():
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards_per_deck=2)
    deck = make_deck()
    quota.reserve_deck_member(USER, deck.pk)
    quota.reserve_deck_member(USER, deck.pk)
    with pytest.raises(QuotaExceeded) as caught:
        quota.reserve_deck_member(USER, deck.pk)
    assert caught.value.extra == {"kind": "cards_per_deck", "used": 2, "limit": 2, "plan": "free"}
    quota.release_deck_member(USER, deck.pk)
    assert RecallDeck.objects.get(pk=deck.pk).card_count == 1


def test_someone_elses_deck_cannot_be_reserved_against():
    deck = make_deck()
    other = make_deck(owner="11111111-1111-4111-8111-111111111111")
    with pytest.raises(QuotaExceeded):
        quota.reserve_deck_member(USER, other.pk)
    assert RecallDeck.objects.get(pk=other.pk).card_count == 0
    assert deck.card_count == 0


def test_reconcile_rebuilds_the_counters_from_the_tables():
    make_item()
    make_item()
    make_item(status="deleted")
    make_deck()
    quota.reserve_cards(USER, 9)
    assert quota.reconcile(USER) == {"cards_active": 2, "decks_active": 1}
    assert usage().cards_active == 2 and usage().reconciled_at is not None
