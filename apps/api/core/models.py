import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UUIDModel(TimeStampedModel):
    """Primary key is a random UUID; timestamps come from TimeStampedModel."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class Job(UUIDModel):
    """
    A durable unit of background work (`core.jobs`). Light jobs run from a cron tick, heavy ones from the always-on worker
    (`manage.py run_worker`). The row is the whole queue: no broker, so it survives deploys and works on serverless.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"  # out of attempts

    ACTIVE_STATUSES = ("queued", "running")

    type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    # While a job with this key is queued or running, enqueueing it again returns that job (see the partial unique index).
    dedupe_key = models.CharField(max_length=200, null=True, blank=True)  # noqa: DJ001 - NULL means no key; the unique index skips it
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.QUEUED)
    priority = models.SmallIntegerField(
        default=0
    )  # higher first; keeps the first chunk of a big job ahead of later ones
    attempts = models.SmallIntegerField(default=0)
    max_attempts = models.SmallIntegerField(default=5)
    run_after = models.DateTimeField(default=timezone.now)
    locked_at = models.DateTimeField(
        null=True, blank=True
    )  # a running job locked longer ago than the timeout is reclaimed
    locked_by = models.CharField(max_length=64, blank=True, default="")
    last_error = models.CharField(max_length=500, blank=True, default="")  # never contains the payload
    result = models.JSONField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "core_job"
        constraints = [
            models.UniqueConstraint(
                fields=["dedupe_key"],
                condition=Q(dedupe_key__isnull=False, status__in=["queued", "running"]),
                name="core_job_dedupe_while_active",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["queued", "running", "done", "failed"]), name="core_job_status_valid"
            ),
        ]
        indexes = [models.Index(fields=["status", "-priority", "run_after"], name="core_job_claim_idx")]

    def __str__(self) -> str:
        return f"{self.type} ({self.status})"
