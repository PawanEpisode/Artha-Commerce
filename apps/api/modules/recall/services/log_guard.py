"""
Switches that lift the review log's protection for one piece of work (ERD 2.8), PostgreSQL only (SQLite has no trigger).

    with log_guard.replaying():   # the replay service rewrites derived columns, `counts_for_scheduling` and `flags`
    with log_guard.erasing():     # account erasure deletes a student's rows

`SET LOCAL` lasts until the end of the outermost transaction, and a savepoint does not end it, so the switch is switched back
off when the block exits. Fact columns never change, whatever the switch says.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from django.db import connection

REPLAYING = "recall.replaying"
ERASING = "recall.erasing"


def _set(name: str, value: str) -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [name, value])


@contextmanager
def _switched(name: str) -> Iterator[None]:
    _set(name, "on")
    try:
        yield
    finally:
        _set(name, "off")


def replaying():
    return _switched(REPLAYING)


def erasing():
    return _switched(ERASING)
