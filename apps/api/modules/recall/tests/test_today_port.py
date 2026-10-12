"""R2-W3 D: recall's tasks for Today (F-13) through `core.today_port`: flag aware, minutes from her own pace."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from core import today_port
from modules.recall import provider
from modules.recall.models import RecallCard, RecallSettings
from modules.recall.selectors import provide_today

from .test_exam_api import FIXED, enrol, mine
from .w5 import ME

pytestmark = pytest.mark.django_db


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(timezone, "now", lambda: FIXED)


def kinds(result):
    return {t.kind: t for t in result.tasks}


def test_the_app_registers_one_recall_provider():
    from django.apps import apps

    apps.get_app_config("recall").ready()
    assert "recall" in today_port.registered_keys()


def test_a_student_with_nothing_has_no_tasks(clock):
    assert provide_today(ME, now=FIXED).tasks == []
    assert provider.today_tasks(ME, now=FIXED).tasks == []


def test_with_the_flag_off_the_result_is_empty(scheme, clock, flag_off):
    mine(scheme, state=2, stability=1.0, last_days=30)
    assert provider.today_tasks(ME, now=FIXED).tasks == []


def test_a_card_waiting_for_still_correct_is_a_recheck_task_with_minutes(scheme, clock):
    card = mine(scheme)
    RecallCard.objects.filter(pk=card.pk).update(needs_recheck=True, recheck_reason="content_changed")
    task = kinds(provider.today_tasks(ME, now=FIXED))["recheck"]
    assert (task.title, task.count) == ("Re-check after amendment", 1)
    assert task.est_minutes >= 1 and task.target == "cards?state=recheck"


def test_quick_revision_appears_within_45_days_of_the_exam(scheme, clock):
    enrol(scheme, FIXED.date() + timedelta(days=37))
    for _ in range(25):
        mine(scheme)
    task = kinds(provider.today_tasks(ME, now=FIXED))["quick_revision"]
    assert task.count >= 1 and task.est_minutes >= 1 and task.target == "quick"


def test_quick_revision_is_not_offered_far_from_the_exam(scheme, clock):
    enrol(scheme, FIXED.date() + timedelta(days=120))
    for _ in range(25):
        mine(scheme)
    assert "quick_revision" not in kinds(provider.today_tasks(ME, now=FIXED))


def test_quick_revision_is_not_offered_on_vacation(scheme, clock):
    enrol(scheme, FIXED.date() + timedelta(days=37))
    for _ in range(25):
        mine(scheme)
    RecallSettings.objects.update_or_create(user_id=ME, defaults={"vacation_until": FIXED.date() + timedelta(days=5)})
    assert "quick_revision" not in kinds(provider.today_tasks(ME, now=FIXED))


def test_through_the_port_the_flag_decides(scheme, clock, monkeypatch):
    mine(scheme)
    card = RecallCard.objects.filter(user_id=ME).first()
    RecallCard.objects.filter(pk=card.pk).update(needs_recheck=True)
    today_port.register_task_provider("recall", provider.today_tasks)
    assert [r.key for r in today_port.collect(ME, now=FIXED)] == ["recall"]


# ---------------------------------------------------------------------------- R2-W4 leftover: "N cards changed"


def test_a_deck_update_applied_today_is_a_cards_changed_task(api):
    from .w22 import card_of, deck_with_student, edit, pointer, publish_next, really_review, unique

    deck, items, sub = deck_with_student(3)
    really_review(card_of(items[0]))
    edit(items[0], pointer(unique("Rewritten")), "substantive")  # comes back for a re-check
    edit(items[1], pointer(unique("Typo")), "typo")  # silent
    publish_next(deck)
    assert "cards_changed" not in kinds(provider.today_tasks(ME, now=timezone.now()))  # nothing applied yet
    assert api.post(f"/recall/subscriptions/{sub.id}/apply-update/").status_code == 200
    task = kinds(provider.today_tasks(ME, now=timezone.now()))["cards_changed"]
    assert (task.count, task.title, task.target) == (2, "2 cards changed in your decks", "decks")
    assert task.est_minutes >= 1


def test_yesterdays_updates_and_removed_cards_are_not_counted(api):
    from modules.recall.models import RecallSubscriptionUpdate
    from modules.recall.selectors import today as today_selectors

    from .w22 import deck_with_student, edit, pointer, publish_next, unique

    deck, items, sub = deck_with_student(3)
    edit(items[0], pointer(unique("Typo")), "typo")
    publish_next(deck, removed=[items[2]])
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    now = timezone.now()
    assert today_selectors.cards_changed(ME, since=now - timedelta(days=1), until=now + timedelta(days=1)) == 1
    RecallSubscriptionUpdate.objects.update(applied_at=now - timedelta(days=2))
    assert today_selectors.cards_changed(ME, since=now - timedelta(days=1), until=now + timedelta(days=1)) == 0


def test_a_single_changed_card_reads_in_the_singular(api):
    from .w22 import deck_with_student, edit, pointer, publish_next, unique

    deck, items, sub = deck_with_student(2)
    edit(items[0], pointer(unique("Typo")), "typo")
    publish_next(deck)
    api.post(f"/recall/subscriptions/{sub.id}/apply-update/")
    assert kinds(provider.today_tasks(ME, now=timezone.now()))["cards_changed"].title == "1 card changed in your decks"
