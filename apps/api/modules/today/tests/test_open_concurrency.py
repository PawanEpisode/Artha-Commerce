"""Two simultaneous opens make one plan (FR-F13-02). Needs PostgreSQL: the single flight is an advisory lock, and SQLite has one writer."""

import threading
import time
import uuid

import pytest
from django.db import connection, connections

from modules.today import services
from modules.today.models import DayPlan, Task
from modules.today.registry import KindSpec

from .conftest import USER
from .helpers import candidate, register_fake

pytestmark = [
    pytest.mark.django_db(transaction=True, serialized_rollback=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="advisory locks are a PostgreSQL feature"),
]


def open_together(count):
    barrier = threading.Barrier(count)
    results, errors = [], []

    def run():
        try:
            barrier.wait(timeout=10)
            results.append(services.open_today(uuid.UUID(USER)))
        except Exception as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run) for _ in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not errors, errors
    return results


def test_simultaneous_opens_give_one_plan_and_one_creator(enrolled):
    def slow(request):  # widens the window in which a second caller would also start generating
        time.sleep(0.4)
        return [candidate("slow:1", subject_id=request.ctx.papers[0].subject_id)]

    calls = register_fake("fake.slow", slow, kinds=[KindSpec("fake_mcq", "practice", "mcq", "x", 10)], timeout_ms=2000)
    results = open_together(4)
    assert len(results) == 4
    assert (
        len(calls) == 1
    )  # single flight: the others waited for the lock and read the finished plan, they did not generate
    assert DayPlan.objects.filter(user_id=USER).count() == 1
    assert sorted(r.created for r in results) == [False, False, False, True]
    assert len({r.plan.id for r in results}) == 1 and len({r.plan.generation_no for r in results}) == 1
    task_ids = set(Task.objects.filter(user_id=USER).values_list("id", flat=True))
    assert (
        len(task_ids) == DayPlan.objects.get(user_id=USER).planned_count
    )  # no duplicated rows from a second generation
