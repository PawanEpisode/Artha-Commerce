"""Quota and idempotency under real concurrency. Needs PostgreSQL (row locks and conditional UPDATE semantics); skipped on SQLite."""

import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import close_old_connections, connection

from modules.notes.errors import QuotaExceeded
from modules.notes.models import Note, QuotaUsage, Tag
from modules.notes.services import notes as note_services
from modules.notes.services import quota, tags

pytestmark = [
    pytest.mark.django_db(transaction=True, serialized_rollback=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="concurrency semantics need PostgreSQL"),
]

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
THREADS = 8


def _race(fn, n=THREADS):
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


def test_only_the_notes_that_fit_are_created():
    quota.ensure_usage(USER)
    QuotaUsage.objects.filter(pk=USER).update(notes_active=2000 - 3)
    results = _race(lambda i: note_services.create_note(USER, client_id=uuid.uuid4(), body_md=f"n{i}") and "ok")
    assert results.count("ok") == 3 and results.count("refused") == THREADS - 3
    assert Note.objects.filter(user_id=USER).count() == 3
    assert QuotaUsage.objects.get(pk=USER).notes_active == 2000


def test_the_same_client_id_creates_one_note_and_counts_once():
    cid = uuid.uuid4()
    results = _race(lambda i: note_services.create_note(USER, client_id=cid, body_md="same").created)
    assert results.count(True) == 1
    assert Note.objects.filter(user_id=USER).count() == 1 and QuotaUsage.objects.get(pk=USER).notes_active == 1


def test_only_the_tags_that_fit_are_created_and_the_same_name_counts_once():
    quota.ensure_usage(USER)
    QuotaUsage.objects.filter(pk=USER).update(tags_count=200 - 2)
    results = _race(lambda i: tags.create_tag(USER, f"tag {i}") and "ok")
    assert results.count("ok") == 2 and Tag.objects.filter(user_id=USER).count() == 2
    assert QuotaUsage.objects.get(pk=USER).tags_count == 200
    Tag.objects.all().delete()
    QuotaUsage.objects.filter(pk=USER).update(tags_count=0)
    same = _race(lambda i: tags.create_tag(USER, "Revise")[1])
    assert same.count(True) == 1 and QuotaUsage.objects.get(pk=USER).tags_count == 1


def test_storage_bytes_never_exceed_the_plan():
    quota.ensure_usage(USER)
    limit = quota.limits_for(USER).storage_bytes
    QuotaUsage.objects.filter(pk=USER).update(bytes_used=limit - 5000)
    results = _race(lambda i: quota.reserve_bytes(USER, 2000) or "ok")
    assert results.count("ok") == 2 and QuotaUsage.objects.get(pk=USER).bytes_used == limit - 1000


def test_monthly_counters_stop_at_the_limit():
    results = _race(lambda i: quota.charge_monthly(USER, "ai_summaries") or "ok")
    assert results.count("ok") == 5 and results.count("refused") == THREADS - 5
