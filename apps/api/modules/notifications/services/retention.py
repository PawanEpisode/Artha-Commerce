"""
The retention job (FR-N24): deletes expired rows in batches of at most 1000, each batch in its own short transaction,
so it never holds a lock for long and can be stopped at any point. Running it again is a no-op.

Order matters only for tidiness: deliveries first (they are the biggest table), then notifications (their remaining
deliveries go with them), then finished jobs, then long-revoked devices (their deliveries keep the row, device NULL), then the shown-message memory.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from ..domain import retention
from ..domain.enums import JobStatus
from ..logs import log_event
from ..models import Delivery, Device, MessageShown, Notification, ScheduledJob


@dataclass(frozen=True)
class PruneResult:
    """Rows deleted (or, for a dry run, that would be deleted) per table, and whether a limit stopped the run early."""

    deliveries: int = 0
    notifications: int = 0
    jobs: int = 0
    revoked_devices: int = 0
    messages_shown: int = 0
    more: bool = False

    @property
    def total(self) -> int:
        return self.deliveries + self.notifications + self.jobs + self.revoked_devices + self.messages_shown


def _querysets(now: datetime) -> dict[str, QuerySet]:
    c = retention.cutoffs(now)
    return {
        "deliveries": Delivery.objects.filter(attempted_at__lt=c.deliveries),
        "notifications": Notification.objects.filter(created_at__lt=c.notifications),
        "jobs": ScheduledJob.objects.filter(updated_at__lt=c.jobs).exclude(status=JobStatus.PENDING),
        "revoked_devices": Device.objects.filter(Q(revoked_at__isnull=False) & Q(revoked_at__lt=c.revoked_devices)),
        "messages_shown": MessageShown.objects.filter(shown_on__lt=c.messages_shown),
    }


def _delete_in_batches(
    qs: QuerySet, *, batch: int, budget: int | None, out_of_time: Callable[[], bool]
) -> tuple[int, bool]:
    """Deletes `qs` a batch at a time. Returns (rows deleted, stopped early because the budget or the clock ran out)."""
    deleted = 0
    while True:
        if out_of_time() or (budget is not None and deleted >= budget):
            return deleted, True
        take = batch if budget is None else min(batch, budget - deleted)
        with transaction.atomic():
            ids = list(qs.order_by("pk").values_list("pk", flat=True)[:take])
            if not ids:
                return deleted, False
            qs.model.objects.filter(pk__in=ids).delete()
        deleted += len(ids)
        if len(ids) < take:
            return deleted, False


def prune(
    *,
    now: datetime | None = None,
    dry_run: bool = False,
    batch: int = retention.BATCH_SIZE,
    max_rows: int | None = None,
    out_of_time: Callable[[], bool] = lambda: False,
) -> PruneResult:
    """
    Prunes every table. `max_rows` bounds the whole run (the sweep uses it); `out_of_time` lets the caller stop between
    batches. A dry run counts and deletes nothing.
    """
    if batch < 1 or batch > retention.BATCH_SIZE:
        raise ValueError(f"batch must be between 1 and {retention.BATCH_SIZE}")
    at = now or timezone.now()
    sets = _querysets(at)
    if dry_run:
        return PruneResult(**{name: qs.count() for name, qs in sets.items()})
    counts: dict[str, int] = {}
    more = False
    left = max_rows
    for name, qs in sets.items():
        done, stopped = _delete_in_batches(qs, batch=batch, budget=left, out_of_time=out_of_time)
        counts[name] = done
        if left is not None:
            left -= done
        if stopped:
            more = True
            break
    result = PruneResult(**counts, more=more)
    if result.total or more:
        log_event(logging.INFO, "prune_run", **counts, more=more)
    return result
