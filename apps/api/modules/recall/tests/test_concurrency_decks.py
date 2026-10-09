"""Subscribing under real concurrency and the advisory lock. Needs PostgreSQL; skipped on SQLite."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections, connection, transaction

from modules.recall.models import RecallCard, RecallSubscription
from modules.recall.services import subscriptions

from .factories import USER
from .w11 import published_deck

pytestmark = [
    pytest.mark.django_db(transaction=True, serialized_rollback=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="advisory locks need PostgreSQL"),
]


def test_racing_subscribes_make_one_subscription_and_one_set_of_cards():
    deck, _, _ = published_deck(3)

    def tap(_):
        close_old_connections()
        try:
            return subscriptions.subscribe(USER, deck.id).created
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(tap, range(8)))
    assert created.count(True) == 1
    assert RecallSubscription.objects.filter(user_id=USER, deck=deck).count() == 1
    assert RecallCard.objects.filter(user_id=USER).count() == 3


def test_a_held_advisory_lock_makes_a_concurrent_subscribe_wait_until_it_is_released():
    deck, _, _ = published_deck(2)
    held, release, outcome = threading.Event(), threading.Event(), {}

    def holder():
        close_old_connections()
        try:
            with transaction.atomic():
                subscriptions._lock(USER, deck.id)
                held.set()
                release.wait(10)
        finally:
            connection.close()

    def tapper():
        close_old_connections()
        try:
            started = time.monotonic()
            outcome["created"] = subscriptions.subscribe(USER, deck.id).created
            outcome["waited"] = time.monotonic() - started
        finally:
            connection.close()

    t1 = threading.Thread(target=holder)
    t1.start()
    assert held.wait(10)
    t2 = threading.Thread(target=tapper)
    t2.start()
    time.sleep(0.6)
    assert t2.is_alive() and "created" not in outcome  # blocked behind the lock
    assert not RecallSubscription.objects.filter(user_id=USER).exists()
    release.set()
    t1.join(10)
    t2.join(10)
    assert outcome["created"] is True and outcome["waited"] >= 0.5
    assert RecallCard.objects.filter(user_id=USER).count() == 2


def test_the_lock_is_per_student_and_deck_so_others_are_not_held_up():
    deck, _, _ = published_deck(1)
    other = __import__("uuid").uuid4()
    held, release = threading.Event(), threading.Event()

    def holder():
        close_old_connections()
        try:
            with transaction.atomic():
                subscriptions._lock(USER, deck.id)
                held.set()
                release.wait(10)
        finally:
            connection.close()

    t = threading.Thread(target=holder)
    t.start()
    assert held.wait(10)
    try:
        started = time.monotonic()
        assert subscriptions.subscribe(other, deck.id).created
        assert time.monotonic() - started < 2
    finally:
        release.set()
        t.join(10)
