"""The review log: checks on both databases; partitions, immutability trigger and RLS on PostgreSQL only (D5)."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from modules.recall.models import RecallReviewLog
from modules.recall.services import log_guard

from .factories import OTHER, USER

pytestmark = pytest.mark.django_db
postgres = pytest.mark.skipif(connection.vendor != "postgresql", reason="partitions and triggers need PostgreSQL")


def log(user=USER, **over) -> RecallReviewLog:
    now = timezone.now()
    fields = {
        "user_id": user,
        "id": uuid.uuid4(),
        "kind": "review",
        "card_id": uuid.uuid4(),
        "item_id": uuid.uuid4(),
        "item_version_id": uuid.uuid4(),
        "rating": 3,
        "reviewed_at": now,
        "received_at": now,
        "local_date": date(2026, 3, 2),
    }
    return RecallReviewLog.objects.create(**{**fields, **over})


def test_a_review_is_stored_with_its_defaults():
    row = log()
    stored = RecallReviewLog.objects.get(user_id=USER, id=row.id)
    assert (stored.mode, stored.counts_for_scheduling, stored.flags, stored.tz_offset_min) == ("normal", True, [], 0)


@pytest.mark.parametrize(
    "bad",
    [
        {"rating": 5},
        {"rating": 0},
        {"rating": None},  # a review needs a rating
        {"kind": "undo"},  # an undo has no rating and a target
        {"kind": "undo", "rating": None},  # ... and needs the target
        {"voids_id": uuid.uuid4()},  # a review does not void anything
        {"kind": "edit"},
        {"mode": "sprint"},
        {"duration_ms": 600_001},
        {"duration_ms": -1},
    ],
)
def test_check_constraints_refuse_bad_rows(bad):
    with pytest.raises(IntegrityError), transaction.atomic():
        log(**bad)


def test_an_undo_is_a_row_with_no_rating_and_a_target():
    target = log()
    undo = log(kind="undo", rating=None, voids_id=target.id)
    assert RecallReviewLog.objects.get(user_id=USER, id=undo.id).voids_id == target.id


def test_the_same_event_cannot_be_voided_twice():
    target = log()
    log(kind="undo", rating=None, voids_id=target.id)
    with pytest.raises(IntegrityError), transaction.atomic():
        log(kind="undo", rating=None, voids_id=target.id)


def test_an_event_id_is_unique_per_student_only():
    row = log()
    with pytest.raises(IntegrityError), transaction.atomic():
        log(id=row.id)
    log(user=OTHER, id=row.id)  # another student may carry the same client id


@postgres
def test_the_table_is_hash_partitioned_into_16_and_rows_are_routed_by_student():
    with connection.cursor() as c:
        c.execute("SELECT relkind FROM pg_class WHERE relname = 'recall_reviewlog'")
        assert c.fetchone()[0] == "p"
        c.execute(
            "SELECT count(*) FROM pg_inherits i JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = 'recall_reviewlog'"
        )
        assert c.fetchone()[0] == 16
    row = log()
    with connection.cursor() as c:
        c.execute("SELECT tableoid::regclass::text FROM recall_reviewlog WHERE id = %s", [row.id])
        assert c.fetchone()[0].startswith("recall_reviewlog_p")
        # the same student always lands in the same partition
        second = log()
        c.execute("SELECT count(DISTINCT tableoid) FROM recall_reviewlog WHERE id IN (%s, %s)", [row.id, second.id])
        assert c.fetchone()[0] == 1


def _sql(statement, params=()):
    with connection.cursor() as c:
        c.execute(statement, params)
        return c.rowcount


@postgres
@pytest.mark.parametrize(
    "column,value",
    [
        ("rating", 1),
        ("reviewed_at", "2020-01-01T00:00:00Z"),
        ("card_id", str(uuid.uuid4())),
        ("mode", "cram"),
        ("local_date", "2020-01-01"),
        ("duration_ms", 5),
    ],
)
def test_a_fact_column_cannot_be_updated_even_when_replaying(column, value):
    row = log()
    with pytest.raises(DatabaseError), transaction.atomic(), log_guard.replaying():
        _sql(f"UPDATE recall_reviewlog SET {column} = %s WHERE user_id = %s AND id = %s", [value, USER, row.id])


@postgres
def test_a_delete_is_refused():
    row = log()
    with pytest.raises(DatabaseError), transaction.atomic():
        _sql("DELETE FROM recall_reviewlog WHERE user_id = %s AND id = %s", [USER, row.id])
    assert RecallReviewLog.objects.filter(user_id=USER, id=row.id).exists()


@postgres
def test_a_delete_is_allowed_while_erasing_and_only_then():
    row = log()
    with transaction.atomic(), log_guard.erasing():
        assert _sql("DELETE FROM recall_reviewlog WHERE user_id = %s AND id = %s", [USER, row.id]) == 1
    assert not RecallReviewLog.objects.filter(user_id=USER, id=row.id).exists()
    other = log()
    with pytest.raises(DatabaseError), transaction.atomic():
        _sql("DELETE FROM recall_reviewlog WHERE user_id = %s AND id = %s", [USER, other.id])


@postgres
@pytest.mark.parametrize(
    "assignment",
    [
        "counts_for_scheduling = false",
        "flags = '[\"late\"]'::jsonb",
        "stability_after = 3.5",
        "scheduled_days = 2",
        "scheduler_version = 'fsrs-6.0'",
    ],
)
def test_derived_columns_change_only_under_replaying(assignment):
    row = log()
    with pytest.raises(DatabaseError), transaction.atomic():
        _sql(f"UPDATE recall_reviewlog SET {assignment} WHERE user_id = %s AND id = %s", [USER, row.id])
    with transaction.atomic(), log_guard.replaying():
        assert _sql(f"UPDATE recall_reviewlog SET {assignment} WHERE user_id = %s AND id = %s", [USER, row.id]) == 1


@postgres
def test_an_update_that_changes_nothing_is_allowed():
    row = log()
    with transaction.atomic():
        assert _sql("UPDATE recall_reviewlog SET rating = rating WHERE user_id = %s AND id = %s", [USER, row.id]) == 1


def test_the_switches_are_harmless_on_any_database():
    with log_guard.replaying(), log_guard.erasing():
        pass
