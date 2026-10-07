"""The retention job (FR-N24): expired rows go in small batches, nothing else is touched, a second run does nothing."""

import io
import logging
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import CommandError, call_command

from modules.notifications.domain.enums import JobKind, JobStatus
from modules.notifications.models import Delivery, Device, Notification, ScheduledJob
from modules.notifications.services import retention
from modules.notifications.tests.helpers import register

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
USER = uuid.uuid4()


def days(n: int) -> datetime:
    return NOW - timedelta(days=n)


def notification(age_days: int) -> Notification:
    n = Notification.objects.create(
        user_id=USER,
        category="timer",
        event="timer_end",
        dedupe_key=f"k:{uuid.uuid4().hex}",
        title="t",
        body="b",
        deep_link="/app/focus",
        priority=0,
    )
    Notification.objects.filter(id=n.id).update(created_at=days(age_days))
    return n


def delivery(n: Notification, age_days: int) -> Delivery:
    # No device: Postgres treats that null as equal, so two of these cannot share a notification.
    return Delivery.objects.create(
        notification=n, user_id=USER, channel="push", status="sent", attempted_at=days(age_days)
    )


def job(status: str, age_days: int) -> ScheduledJob:
    j = ScheduledJob.objects.create(
        user_id=USER, kind=JobKind.TIMER_END, subject_key=uuid.uuid4().hex, fire_at=days(age_days), status=status
    )
    ScheduledJob.objects.filter(id=j.id).update(updated_at=days(age_days))
    return j


def device(revoked_days_ago: int | None) -> Device:
    d = register(uuid.uuid4(), now=NOW).device
    if revoked_days_ago is not None:
        Device.objects.filter(id=d.id).update(revoked_at=days(revoked_days_ago), revoked_reason="gone")
    return d


def test_deliveries_older_than_90_days_go_and_newer_ones_stay():
    old, edge, new = delivery(notification(10), 91), delivery(notification(10), 90), delivery(notification(10), 89)
    result = retention.prune(now=NOW)
    assert result.deliveries == 1
    assert not Delivery.objects.filter(id=old.id).exists()
    assert Delivery.objects.filter(id__in=[edge.id, new.id]).count() == 2


def test_notifications_older_than_180_days_go_with_their_deliveries():
    old, fresh = notification(181), notification(179)
    delivery(old, 10)
    keep = delivery(fresh, 10)
    result = retention.prune(now=NOW)
    assert result.notifications == 1
    assert list(Notification.objects.values_list("id", flat=True)) == [fresh.id]
    assert list(Delivery.objects.values_list("id", flat=True)) == [keep.id]


def test_only_finished_jobs_older_than_30_days_go():
    stale_pending = job(JobStatus.PENDING, 90)  # a pending job is work still to do, however old
    gone = [job(s, 31) for s in (JobStatus.FIRED, JobStatus.SKIPPED, JobStatus.CANCELLED, JobStatus.FAILED)]
    recent = job(JobStatus.FIRED, 29)
    result = retention.prune(now=NOW)
    assert result.jobs == 4
    assert set(ScheduledJob.objects.values_list("id", flat=True)) == {stale_pending.id, recent.id}
    assert not ScheduledJob.objects.filter(id__in=[j.id for j in gone]).exists()


def test_only_devices_revoked_more_than_30_days_ago_go():
    active, recently, long_ago = device(None), device(5), device(31)
    result = retention.prune(now=NOW)
    assert result.revoked_devices == 1
    assert set(Device.objects.values_list("id", flat=True)) == {active.id, recently.id}
    assert not Device.objects.filter(id=long_ago.id).exists()


def test_a_device_deleted_keeps_its_delivery_rows_without_the_device():
    n = notification(10)
    d = device(40)
    row = Delivery.objects.create(
        notification=n, user_id=USER, device=d, channel="push", status="sent", attempted_at=days(5)
    )
    retention.prune(now=NOW)
    row.refresh_from_db()
    assert row.device_id is None


def test_running_it_again_is_a_no_op():
    delivery(notification(10), 100)
    job(JobStatus.FIRED, 40)
    first = retention.prune(now=NOW)
    second = retention.prune(now=NOW)
    assert first.total == 2 and second.total == 0 and not second.more


def test_it_deletes_in_batches_and_stops_at_the_row_limit():
    for _ in range(5):
        delivery(notification(10), 100)
    deliveries_before = Delivery.objects.count()
    part = retention.prune(now=NOW, batch=2, max_rows=3)
    assert part.deliveries == 3 and part.more
    assert Delivery.objects.count() == deliveries_before - 3
    rest = retention.prune(now=NOW, batch=2)
    assert rest.deliveries == 2 and not rest.more and Delivery.objects.count() == 0


def test_the_clock_can_stop_the_job_between_batches():
    for _ in range(4):
        delivery(notification(10), 100)
    calls = {"n": 0}

    def out_of_time():
        calls["n"] += 1
        return calls["n"] > 1  # one batch is allowed, then the clock says stop

    result = retention.prune(now=NOW, batch=2, out_of_time=out_of_time)
    assert result.deliveries == 2 and result.more


@pytest.mark.parametrize("batch", [0, 1001, -1])
def test_a_batch_over_1000_or_below_1_is_refused(batch):
    with pytest.raises(ValueError):
        retention.prune(now=NOW, batch=batch)


def test_a_dry_run_counts_and_deletes_nothing():
    delivery(notification(10), 100)
    job(JobStatus.FIRED, 40)
    result = retention.prune(now=NOW, dry_run=True)
    assert (result.deliveries, result.jobs, result.total) == (1, 1, 2)
    assert Delivery.objects.count() == 1 and ScheduledJob.objects.count() == 1


def test_a_run_that_deleted_something_logs_prune_run(caplog):
    delivery(notification(10), 100)
    caplog.set_level(logging.INFO)
    retention.prune(now=NOW)
    (line,) = [r for r in caplog.records if r.getMessage().startswith("prune_run ")]
    assert line.push["deliveries"] == 1 and line.push["more"] is False


def test_a_run_that_found_nothing_stays_silent(caplog):
    caplog.set_level(logging.INFO)
    retention.prune(now=NOW)
    assert not [r for r in caplog.records if r.getMessage().startswith("prune_run")]


def run(*args):
    out = io.StringIO()
    call_command("prune_notifications", *args, stdout=out)
    return out.getvalue()


def test_the_command_prints_counts_per_table_and_deletes_nothing_on_a_dry_run():
    delivery(notification(10), 1000)
    text = run("--dry-run")
    assert "deliveries: would delete 1" in text and "notifications: would delete 0" in text
    assert Delivery.objects.count() == 1


def test_the_command_deletes_and_reports():
    delivery(notification(10), 1000)
    assert "deliveries: deleted 1" in run()
    assert Delivery.objects.count() == 0
    assert "deliveries: deleted 0" in run()


def test_the_command_refuses_a_batch_over_1000():
    with pytest.raises(CommandError):
        run("--batch", "5000")
