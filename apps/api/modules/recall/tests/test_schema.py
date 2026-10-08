"""Constraints, defaults and seeds of the recall tables (ERD 2). Every enum has a check; the new-card pair is enforced."""

from __future__ import annotations

import importlib.util
import uuid

import pytest
from django.db import IntegrityError, transaction

from modules.recall.domain import fsrs6
from modules.recall.models import (
    RecallCard,
    RecallDeck,
    RecallItem,
    RecallItemVersion,
    RecallParams,
    RecallQuotaPlan,
    RecallSettings,
)

from .factories import OTHER, USER, fingerprint, make_card, make_deck, make_item, reviewed_fields

pytestmark = pytest.mark.django_db


def refused(**fields) -> bool:
    try:
        with transaction.atomic():
            RecallItem.objects.create(**fields)
    except IntegrityError:
        return True
    return False


ITEM = {"kind": "pointer", "ownership": "user", "owner_user_id": USER}


def item_fields(**over):
    return {**ITEM, "fingerprint": fingerprint(str(uuid.uuid4())), **over}


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "essay"},
        {"ownership": "group"},
        {"origin": "telepathy"},
        {"status": "gone"},
        {"importance": "huge"},
        {"rights_status": "free_for_all"},
        {"fingerprint": "not-a-hash"},
        {"ownership": "platform"},  # a platform item has no owner
        {"owner_user_id": None},  # a user item has an owner
    ],
)
def test_item_enums_and_owner_rule_are_enforced(bad):
    assert refused(**item_fields(**bad))


def test_a_valid_item_is_accepted():
    assert not refused(**item_fields())
    assert not refused(**item_fields(ownership="platform", owner_user_id=None))


def test_external_ref_and_client_id_are_idempotency_keys():
    assert not refused(**item_fields(external_ref="seed:a"))
    assert refused(**item_fields(external_ref="seed:a"))
    cid = uuid.uuid4()
    assert not refused(**item_fields(client_id=cid))
    assert refused(**item_fields(client_id=cid))
    assert not refused(**item_fields(client_id=cid, owner_user_id=OTHER))  # another student may reuse the id


def test_a_source_card_is_unique_per_student_object_and_port_kind():
    src = {"origin_module": "notes", "origin_ref": "mark-1", "origin_kind": "formula"}
    assert not refused(**item_fields(**src))
    assert refused(**item_fields(**src))
    assert not refused(**item_fields(**{**src, "origin_kind": "definition"}))
    assert not refused(**item_fields(**src, status="deleted") | {"origin_ref": "mark-2"})


def test_one_live_version_per_item():
    item = make_item()
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallItemVersion.objects.create(
            item=item, version_no=2, state="live", fields={"v": 1}, content_hash=fingerprint("z"), plain_text="z"
        )


def test_version_numbers_are_unique_per_item():
    item = make_item()
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallItemVersion.objects.create(
            item=item, version_no=1, state="superseded", fields={"v": 1}, content_hash=fingerprint("z"), plain_text="z"
        )


def test_deck_owner_rule_and_slug_uniqueness():
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallDeck.objects.create(kind="platform", owner_user_id=USER, title="x")
    RecallDeck.objects.create(kind="platform", slug="gst", title="GST")
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallDeck.objects.create(kind="platform", slug="gst", title="GST 2")
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallDeck.objects.create(kind="user", owner_user_id=USER, title="x", status="weird")


def test_a_new_card_has_no_memory_and_a_reviewed_card_has_it():
    card = make_card()
    assert (card.state, card.stability, card.due_at) == (0, None, None)
    reviewed = make_card(**reviewed_fields())
    assert reviewed.stability == pytest.approx(2.3)


@pytest.mark.parametrize(
    "bad",
    [
        {"state": 0, "stability": 1.0},  # new but has stability
        {"state": 2, "difficulty": 5.0},  # reviewed but no stability and no due
        {"state": 4},
        {"importance": 3},
        {"status": "frozen"},
        {**reviewed_fields(), "difficulty": 11.0},
        {**reviewed_fields(), "difficulty": 0.5},
        {**reviewed_fields(), "stability": 0.0},
    ],
)
def test_card_constraints(bad):
    item = make_item()
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallCard.objects.create(user_id=USER, item=item, item_version=item.live_version, **bad)


def test_a_student_has_one_card_per_item_and_ordinal():
    card = make_card()
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallCard.objects.create(user_id=USER, item=card.item, item_version=card.item_version)
    RecallCard.objects.create(user_id=USER, item=card.item, item_version=card.item_version, ordinal=1)
    RecallCard.objects.create(user_id=OTHER, item=card.item, item_version=card.item_version)


def test_settings_defaults_and_ranges():
    s = RecallSettings.objects.create(user_id=USER)
    assert (s.new_per_day, s.reviews_per_day, s.day_start_hour, s.max_interval_days) == (10, 100, 4, 365)
    assert (s.learning_steps_min, s.relearning_steps_min, s.tz) == ([1, 10], [10], "Asia/Kolkata")
    assert str(s.desired_retention) == "0.90"
    for bad in ({"new_per_day": 101}, {"reviews_per_day": 19}, {"day_start_hour": 7}, {"desired_retention": "0.98"}):
        with pytest.raises(IntegrityError), transaction.atomic():
            RecallSettings.objects.create(user_id=uuid.uuid4(), **bad)


def test_the_default_parameter_set_is_seeded_once_and_equals_the_domain_defaults():
    row = RecallParams.objects.get(scope="default", status="active")
    assert row.scheduler_version == "fsrs-6.0"
    assert list(row.weights) == list(fsrs6.DEFAULT_WEIGHTS)
    assert len(row.weights) == 21
    fsrs6.validate_weights(row.weights)
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallParams.objects.create(scope="default", weights=list(fsrs6.DEFAULT_WEIGHTS))


@pytest.mark.skipif(importlib.util.find_spec("fsrs") is None, reason="py-fsrs is the oracle and is a dev dependency")
def test_the_seeded_weights_equal_the_py_fsrs_defaults():
    from fsrs import Scheduler

    row = RecallParams.objects.get(scope="default", status="active")
    assert list(row.weights) == pytest.approx(list(Scheduler().parameters))


def test_the_plans_are_seeded_from_the_prd():
    free, pro = RecallQuotaPlan.objects.get(pk="free"), RecallQuotaPlan.objects.get(pk="pro")
    assert (free.max_cards, free.max_cards_per_deck, free.max_decks, free.pack_size) == (1500, 500, 100, 300)
    assert (pro.max_cards, pro.max_cards_per_deck, pro.max_decks, pro.pack_size) == (20000, 2000, 500, 500)


def test_deck_member_counter_cannot_go_negative():
    deck = make_deck()
    with pytest.raises(IntegrityError), transaction.atomic():
        RecallDeck.objects.filter(pk=deck.pk).update(card_count=-1)
