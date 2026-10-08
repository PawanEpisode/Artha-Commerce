"""Quota under real concurrency. Needs PostgreSQL (row locks and conditional UPDATE semantics); skipped on SQLite."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections, connection

from modules.recall.errors import QuotaExceeded
from modules.recall.models import RecallDeck, RecallQuotaPlan, RecallQuotaUsage
from modules.recall.services import quota

from .factories import USER, make_deck

pytestmark = [
    pytest.mark.django_db(transaction=True, serialized_rollback=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="concurrency semantics need PostgreSQL"),
]

THREADS = 8


def race(fn, n=THREADS):
    def run(i):
        close_old_connections()
        try:
            fn(i)
            return "ok"
        except QuotaExceeded:
            return "refused"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(run, range(n)))


def test_only_the_cards_that_fit_are_reserved():
    quota.ensure_usage(USER)
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=3)
    results = race(lambda i: quota.reserve_cards(USER))
    assert results.count("ok") == 3 and results.count("refused") == THREADS - 3
    assert RecallQuotaUsage.objects.get(pk=USER).cards_active == 3


def test_only_the_deck_members_that_fit_are_reserved():
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards_per_deck=2)
    deck = make_deck()
    results = race(lambda i: quota.reserve_deck_member(USER, deck.pk))
    assert results.count("ok") == 2
    assert RecallDeck.objects.get(pk=deck.pk).card_count == 2


def test_two_students_do_not_share_a_counter():
    other = uuid.uuid4()
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=1)
    results = race(lambda i: quota.reserve_cards(USER if i % 2 else other), n=4)
    assert results.count("ok") == 2
