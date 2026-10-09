import uuid
from datetime import date, timedelta

import pytest
from django.apps import apps
from django.utils import timezone

from core import registry
from modules.recall.models import (
    RecallAuditLog,
    RecallCard,
    RecallChapterRollup,
    RecallDailyRollup,
    RecallDeck,
    RecallItem,
    RecallItemVersion,
    RecallParams,
    RecallQuotaUsage,
    RecallReport,
    RecallReviewLog,
    RecallScheduleEvent,
    RecallSession,
    RecallSettings,
    RecallSubscription,
)
from modules.recall.services import erasure

from .factories import OTHER, USER, make_card, make_deck, make_item
from .w11 import published_deck

pytestmark = pytest.mark.django_db
USER_COLUMNS = ("user_id", "owner_user_id", "reporter_user_id")


def fill(user, deck, items):
    """One of everything recall can hold for this student."""
    from modules.recall.services import subscriptions

    subscriptions.subscribe(user, deck.id)
    own = make_item(user)
    card = make_card(own, owner=user)
    now = timezone.now()
    session = RecallSession.objects.create(
        user_id=user, client_id=uuid.uuid4(), source="today", started_at=now, last_event_at=now, tz="Asia/Kolkata",
        local_date=date(2026, 10, 1),
    )  # fmt: skip
    RecallScheduleEvent.objects.create(user_id=user, card=card, kind="suspend", at=now)
    for n in range(3):
        RecallReviewLog.objects.create(
            user_id=user, id=uuid.uuid4(), card_id=card.id, item_id=own.id, item_version_id=own.live_version_id,
            rating=3, reviewed_at=now + timedelta(seconds=n), received_at=now, local_date=date(2026, 10, 1),
            session_id=session.id,
        )  # fmt: skip
    RecallDailyRollup.objects.create(user_id=user, local_date=date(2026, 10, 1), good=3)
    RecallChapterRollup.objects.create(user_id=user, local_date=date(2026, 10, 1), reviews=3)
    RecallSettings.objects.update_or_create(user_id=user, defaults={"leech_threshold": 4})
    RecallQuotaUsage.objects.update_or_create(pk=user, defaults={"cards_active": 1})
    RecallParams.objects.create(scope="user", user_id=user, weights=[1.0] * 21)
    RecallReport.objects.create(target_kind="item", target_id=items[0].id, reporter_user_id=user, reason="wrong")
    make_deck(user)


def rows_for(user) -> dict:
    out = {}
    for model in apps.get_app_config("recall").get_models():
        if model is RecallAuditLog:
            continue
        for column in USER_COLUMNS:
            if column in {f.name for f in model._meta.get_fields()}:
                out[model.__name__] = out.get(model.__name__, 0) + model.objects.filter(**{column: user}).count()
        if model is RecallSettings or model is RecallQuotaUsage:
            out[model.__name__] = model.objects.filter(pk=user).count()
    return out


def test_erase_leaves_no_row_for_the_student_in_any_recall_table():
    deck, items, _ = published_deck(2)
    fill(USER, deck, items)
    before = rows_for(USER)
    assert before["RecallReviewLog"] == 3 and before["RecallCard"] >= 3 and sum(before.values()) > 10
    report = erasure.delete_all_for_user(USER)
    assert report["reviewlog"] == 3
    assert {k: v for k, v in rows_for(USER).items() if v} == {}
    assert not RecallItemVersion.objects.filter(item__owner_user_id=USER).exists()
    assert not RecallItem.objects.filter(owner_user_id=USER).exists()
    assert not RecallDeck.objects.filter(owner_user_id=USER).exists()
    assert not RecallSubscription.objects.filter(user_id=USER).exists()
    assert erasure.delete_all_for_user(USER)["cards"] == 0  # idempotent


def test_erase_leaves_other_students_and_the_platform_alone():
    deck, items, _ = published_deck(2)
    fill(USER, deck, items)
    fill(OTHER, deck, items)
    other_before = rows_for(OTHER)
    erasure.delete_all_for_user(USER)
    assert rows_for(OTHER) == other_before
    assert RecallDeck.objects.filter(pk=deck.pk, kind="platform").exists()
    assert RecallItem.objects.filter(ownership="platform").count() == 2


def test_erase_api_needs_the_confirm_word_and_works_with_the_flag_off(api, flag_off):
    deck, items, _ = published_deck(1)
    fill(USER, deck, items)
    assert api.post("/recall/erase/", {}).status_code == 400
    assert api.post("/recall/erase/", {"confirm": "erase"}).status_code == 400
    assert RecallCard.objects.filter(user_id=USER).exists()
    res = api.post("/recall/erase/", {"confirm": "ERASE"})
    assert res.status_code == 200 and res.json_body["deleted"]["cards"] >= 1
    assert {k: v for k, v in rows_for(USER).items() if v} == {}


def test_the_audit_log_is_kept_and_holds_no_student_rows():
    RecallAuditLog.objects.create(actor_id=USER, action="deck_publish", target_kind="deck", target_id="x")
    erasure.delete_all_for_user(USER)
    assert RecallAuditLog.objects.count() == 1


def test_recall_is_registered_with_the_account_registry():
    assert "recall" in [n for n, _ in registry.erasers()] and "recall" in [n for n, _ in registry.exporters()]
