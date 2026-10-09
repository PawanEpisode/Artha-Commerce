"""Idempotency and quota of card creation under real concurrency. Needs PostgreSQL; skipped on SQLite."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections, connection

from core.recall_port import SourceRef
from modules.recall.errors import QuotaExceeded
from modules.recall.models import RecallCard, RecallItem, RecallQuotaPlan, RecallQuotaUsage
from modules.recall.provider import RecallProviderImpl
from modules.recall.services import cards as services

from .factories import USER

pytestmark = [
    pytest.mark.django_db(transaction=True, serialized_rollback=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="concurrency semantics need PostgreSQL"),
]

THREADS = 8
POINTER = {"prompt_md": "When is ITC blocked?", "answer_md": "Under section 17(5)."}


def race(fn, n=THREADS):
    def run(i):
        close_old_connections()
        try:
            return fn(i)
        except QuotaExceeded:
            return "refused"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(run, range(n)))


def test_one_client_id_sent_by_many_requests_makes_one_card():
    client_id = uuid.uuid4()
    results = race(
        lambda i: services.create_card(USER, kind="pointer", fields=dict(POINTER), client_id=client_id, force=True)
    )
    assert len({r.card_id for r in results}) == 1 and sum(not r.existing for r in results) == 1
    assert RecallItem.objects.count() == 1 and RecallCard.objects.count() == 1
    assert RecallQuotaUsage.objects.get(pk=USER).cards_active == 1


def test_only_the_cards_that_fit_the_plan_are_created():
    RecallQuotaPlan.objects.filter(pk="free").update(max_cards=3)
    results = race(
        lambda i: services.create_card(
            USER, kind="pointer", fields={"prompt_md": f"Q{i}?", "answer_md": f"A{i}"}, client_id=uuid.uuid4()
        )
    )
    assert results.count("refused") == THREADS - 3
    assert RecallCard.objects.count() == 3 and RecallQuotaUsage.objects.get(pk=USER).cards_active == 3


def test_the_provider_makes_one_card_per_source_and_kind_whatever_the_client_ids():
    ref = uuid.uuid4()
    provider = RecallProviderImpl()
    results = race(
        lambda i: provider.create_card_from_source(
            USER,
            kind="rule",
            front_md="Why?",
            back_md="Because.",
            source=SourceRef("notes", "annotation", ref),
            client_id=uuid.uuid4(),
        )
    )
    assert len({r.id for r in results}) == 1 and sum(not r.existing for r in results) == 1
    assert RecallItem.objects.count() == 1 and RecallQuotaUsage.objects.get(pk=USER).cards_active == 1
