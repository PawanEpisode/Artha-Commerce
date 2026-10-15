"""
The W3 exit checks, on PostgreSQL where the row locks are real:

- replayed and out-of-order events change nothing, even when delivered at the same moment from several workers;
- done beats a stale skip however the two requests interleave;
- the plan's counters equal the aggregate of its rows after any sequence of actions (random, seeded).
"""

import random
import threading
import uuid
from datetime import timedelta

import pytest
from django.db import connection, connections
from django.utils import timezone

from core import events
from core.errors import QuotaExceeded
from modules.today import actions, completion
from modules.today.errors import (
    InvalidTransitionError,
    NoAlternative,
    PlanChanged,
    StateConflict,
    TaskNotFound,
    UndoExpiredError,
)
from modules.today.models import DayPlan, Task, TaskEvidence
from modules.today.registry import CompletionRule, KindSpec

from .conftest import USER
from .helpers import candidate, cid, local_today, register_fake, register_many, register_practice
from .test_completion import EVENT, make_plan, make_task, provider
from .test_task_actions import reference_counts, stored_counts

pytestmark = [
    pytest.mark.django_db(transaction=True, serialized_rollback=True),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="row locks are a PostgreSQL feature"),
]

UID = uuid.UUID(USER)


def together(*jobs):
    """Runs each callable on its own connection, released at the same moment. Returns (results, errors) in job order."""
    barrier = threading.Barrier(len(jobs))
    out = [None] * len(jobs)

    def run(i, job):
        try:
            barrier.wait(timeout=10)
            out[i] = ("ok", job())
        except Exception as exc:  # noqa: BLE001 - classified by the caller
            out[i] = ("error", exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run, args=(i, j)) for i, j in enumerate(jobs)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert all(o is not None for o in out), "a worker did not finish"
    return out


def assert_counters_match(plan_id):
    assert stored_counts(plan_id) == reference_counts(plan_id)


# ---- events -----------------------------------------------------------------------------------------------------------------


def test_the_same_event_from_five_workers_is_applied_once(enrolled):
    provider()
    plan = make_plan(local_today())
    task = make_task(plan, target=10)
    results = together(*[lambda: completion.handle(EVENT, _payload("same", n=4)) for _ in range(5)])
    assert all(kind == "ok" for kind, _ in results)
    row = Task.objects.get(pk=task.pk)
    assert (row.state, row.progress_value) == ("suggested", 4)
    assert TaskEvidence.objects.filter(task=task).count() == 1


def test_distinct_events_in_parallel_add_up_and_complete_exactly_once(enrolled):
    provider()
    plan = make_plan(local_today())
    task = make_task(plan, target=9)
    jobs = [lambda k=k: completion.handle(EVENT, _payload(k, n=3)) for k in ("a", "b", "c", "a", "b", "c")]
    results = together(*jobs)
    assert all(kind == "ok" for kind, _ in results)
    row = Task.objects.get(pk=task.pk)
    assert (row.state, row.progress_value, row.completed_via) == ("done", 9, "event")
    assert TaskEvidence.objects.filter(task=task).count() == 3
    plan.refresh_from_db()
    assert plan.done_count == 1
    assert_counters_match(plan.id)


def _payload(key, **extra):
    return {
        "user_id": USER,
        "event_id": key,
        "occurred_at": timezone.now().isoformat(),
        "work": "w1",
        **extra,
    }


# ---- done beats a stale skip, however the two requests interleave -----------------------------------------------------------


@pytest.mark.parametrize("round_", range(8))
def test_complete_and_a_newer_skip_at_the_same_moment_always_end_done(enrolled, round_):
    provider()
    plan = make_plan(local_today())
    task = make_task(plan)
    later = timezone.now() + timedelta(minutes=1)
    results = together(
        lambda: actions.complete_task(UID, task.id, client_id=uuid.uuid4()),
        lambda: actions.skip_task(UID, task.id, client_id=uuid.uuid4(), client_ts=later),
    )
    row = Task.objects.get(pk=task.pk)
    assert row.state == "done" and row.skip_reason is None
    complete_result, skip_result = results
    assert complete_result[0] == "ok"
    assert skip_result[0] == "ok" or isinstance(
        skip_result[1], StateConflict
    )  # skip first (then overwritten) or refused
    plan.refresh_from_db()
    assert_counters_match(plan.id)
    assert (plan.done_count, plan.skipped_count) == (1, 0)


def test_two_devices_tapping_complete_together_complete_once(enrolled):
    provider()
    plan = make_plan(local_today())
    task = make_task(plan)
    results = together(*[lambda: actions.complete_task(UID, task.id, client_id=uuid.uuid4()) for _ in range(4)])
    assert all(kind == "ok" for kind, _ in results)
    plan.refresh_from_db()
    assert plan.done_count == 1 and Task.objects.get(pk=task.pk).version == 2
    assert_counters_match(plan.id)


def test_an_event_and_a_manual_tick_at_the_same_moment_complete_once(enrolled):
    provider()
    plan = make_plan(local_today())
    task = make_task(plan)
    together(
        lambda: actions.complete_task(UID, task.id, client_id=uuid.uuid4()),
        lambda: completion.handle(EVENT, _payload("e1", exact=True)),
    )
    plan.refresh_from_db()
    row = Task.objects.get(pk=task.pk)
    assert row.state == "done" and row.completed_via in ("manual", "event") and plan.done_count == 1
    assert_counters_match(plan.id)


def test_two_own_task_adds_with_one_client_id_make_one_task(enrolled):
    cid_ = uuid.uuid4()
    results = together(
        *[lambda: actions.add_task(UID, client_id=cid_, title="Same", local_date=None, est_minutes=5) for _ in range(4)]
    )
    assert all(kind == "ok" for kind, _ in results)
    assert Task.objects.filter(user_id=USER, origin="user").count() == 1
    assert sorted(r[1][1] for r in results) == [False, False, False, True]
    plan = DayPlan.objects.get(user_id=USER)
    assert plan.planned_count == 1


def test_the_daily_quota_holds_under_a_burst(enrolled):
    results = together(
        *[
            lambda n=n: actions.add_task(UID, client_id=uuid.uuid4(), title=f"T{n}", local_date=None, est_minutes=5)
            for n in range(26)
        ]
    )
    created = [r for r in results if r[0] == "ok"]
    refused = [r for r in results if r[0] == "error"]
    assert len(created) == 20 and all(isinstance(r[1], QuotaExceeded) for r in refused)
    assert Task.objects.filter(user_id=USER, origin="user").count() == 20


def test_two_regenerations_with_the_same_expectation_make_one_new_generation(enrolled):
    register_practice()
    register_many()
    body = actions.services.open_today(UID).plan
    results = together(
        *[
            lambda: actions.regenerate(
                UID, expected_generation=body.generation_no, reason="manual", client_id=uuid.uuid4()
            )
            for _ in range(3)
        ]
    )
    winners = [r for r in results if r[0] == "ok"]
    losers = [r for r in results if r[0] == "error"]
    assert len(winners) == 1 and all(isinstance(r[1], PlanChanged) for r in losers)
    plan = DayPlan.objects.get(user_id=USER)
    assert plan.generation_no == body.generation_no + 1
    assert_counters_match(plan.id)
    live_keys = list(
        Task.objects.filter(plan=plan, deleted_at__isnull=True)
        .exclude(state="expired")
        .values_list("dedupe_key", flat=True)
    )
    assert len(live_keys) == len(set(live_keys))


def test_a_regenerate_and_a_tick_at_the_same_moment_both_survive(enrolled):
    register_practice()
    register_many()
    plan = actions.services.open_today(UID).plan
    task = Task.objects.filter(plan=plan, state="suggested").order_by("position").first()
    together(
        lambda: actions.regenerate(
            UID, expected_generation=plan.generation_no, reason="manual", client_id=uuid.uuid4()
        ),
        lambda: actions.complete_task(UID, task.id, client_id=uuid.uuid4()),
    )
    row = Task.objects.get(pk=task.pk)
    assert row.state in (
        "done",
        "expired",
    )  # ticked first (kept as done) or replaced first (then it is gone: not found / invalid)
    if row.state == "expired":
        assert row.end_reason == "regenerated"
    plan.refresh_from_db()
    assert_counters_match(plan.id)


# ---- the counters equal the aggregate after random transitions --------------------------------------------------------------


ACTION_NAMES = [
    "start",
    "complete",
    "skip",
    "snooze",
    "swap",
    "undo_done",
    "undo_skip",
    "event",
    "edit",
    "delete",
    "undo_delete",
    "add",
    "regenerate",
]


@pytest.mark.parametrize("seed", range(12))
def test_counters_equal_the_aggregate_after_random_actions(enrolled, seed):
    rng = random.Random(seed)
    register_practice()
    register_many()
    register_fake(
        "fake.extra",
        lambda request: [candidate(f"extra:{n}", "extra_mcq", None, 6, (80, 80, 80, 80)) for n in range(4)],
        kinds=[KindSpec("extra_mcq", "practice", "mcq", "ListChecks", 6)],
        completion=[CompletionRule(EVENT, lambda e, t: None)],
    )
    actions.services.save_settings(UID, {"minutes_per_day": 240})
    plan = actions.services.open_today(UID).plan
    ref = {"plan": plan}
    expected_errors = (
        InvalidTransitionError,
        StateConflict,
        NoAlternative,
        UndoExpiredError,
        TaskNotFound,
        PlanChanged,
        QuotaExceeded,
        actions.ProviderTaskReadOnly,
    )

    def pick(*states):
        rows = list(Task.objects.filter(user_id=USER, deleted_at__isnull=True))
        if states:
            rows = [t for t in rows if t.state in states]
        return rng.choice(rows) if rows else None

    ts = timezone.now()
    for step in range(60):
        name = rng.choice(ACTION_NAMES)
        task = pick()
        try:
            if name == "start" and task:
                actions.start_task(UID, task.id, client_id=uuid.uuid4())
            elif name == "complete" and task:
                actions.complete_task(UID, task.id, client_id=uuid.uuid4(), client_ts=ts + timedelta(seconds=step))
            elif name == "skip" and task:
                actions.skip_task(UID, task.id, client_id=uuid.uuid4(), reason=rng.choice([None, "no_time", "other"]))
            elif name == "snooze" and task:
                actions.snooze_task(
                    UID, task.id, client_id=uuid.uuid4(), until=rng.choice(["tomorrow", "in_3_days", "next_week"])
                )
            elif name == "swap" and task:
                actions.swap_task(UID, task.id, client_id=uuid.uuid4())
            elif name == "undo_done" and task:
                actions.undo_task(UID, task.id, client_id=uuid.uuid4(), from_state="done")
            elif name == "undo_skip" and task:
                actions.undo_task(UID, task.id, client_id=uuid.uuid4(), from_state="skipped")
            elif name == "event" and task:
                completion.apply_evidence(
                    UID,
                    task.id,
                    event_name=EVENT,
                    event_key=f"k{rng.randrange(6)}",  # keys repeat on purpose: replays
                    delta=rng.choice([0, 1, 2]),
                    completes=rng.random() < 0.3,
                    occurred_at=timezone.now(),
                )
            elif name == "edit" and task:
                actions.edit_task(UID, task.id, {"est_minutes": rng.randint(1, 60)}, version=task.version)
            elif name == "delete" and task:
                actions.delete_task(UID, task.id)
            elif name == "undo_delete":
                gone = list(Task.objects.filter(user_id=USER, deleted_at__isnull=False))
                if gone:
                    actions.undo_task(UID, rng.choice(gone).id, client_id=uuid.uuid4(), from_state="deleted")
            elif name == "add":
                actions.add_task(
                    UID, client_id=uuid.uuid4(), title="Own", local_date=None, est_minutes=rng.randint(1, 30)
                )
            elif name == "regenerate":
                current = DayPlan.objects.get(pk=ref["plan"].pk)
                actions.regenerate(
                    UID, expected_generation=current.generation_no, reason="manual", client_id=uuid.uuid4()
                )
        except expected_errors:
            pass
        for p in DayPlan.objects.filter(user_id=USER):
            assert stored_counts(p.id) == reference_counts(p.id), f"seed {seed} step {step} after {name}"
            assert p.open_minutes >= 0 and p.planned_minutes >= 0
    # nothing is left in a state the database would refuse
    for t in Task.objects.filter(user_id=USER):
        assert (t.state == "done") == (t.completed_at is not None)
        assert (t.state == "snoozed") == (t.snoozed_until is not None)
    live = list(
        Task.objects.filter(user_id=USER, deleted_at__isnull=True)
        .exclude(state="expired")
        .values_list("plan_id", "dedupe_key")
    )
    assert len(live) == len(set(live)), "a unit of work appears twice in one day"
    assert events and cid  # imported helpers used by the other tests in this module
