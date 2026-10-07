"""
Files owned by students (`media_attachment`): one row per object in Supabase Storage. The row, not the object, is what
other modules reference by foreign key, so they never touch bucket or path. What kinds exist and what they may hold is
decided by the registry in `registry.py`, not by a check constraint, so a new feature adds a kind without a migration here.
"""

from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import UUIDModel


class Attachment(UUIDModel):
    class Status(models.TextChoices):
        RESERVED = "reserved", "Reserved"  # quota taken, signed URL issued, bytes not confirmed
        UPLOADED = "uploaded", "Uploaded"  # bytes are in storage, waiting for the scanner
        CLEAN = "clean", "Clean"  # safe to reference and to serve
        REJECTED = "rejected", "Rejected"
        DELETING = "deleting", "Deleting"  # queued for removal from storage

    user_id = models.UUIDField(db_index=True)
    kind = models.CharField(max_length=32)
    bucket = models.CharField(max_length=64)
    path = models.CharField(max_length=512)  # never contains a file name or a title
    bytes = models.BigIntegerField()
    mime = models.CharField(max_length=100)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RESERVED)
    status_reason = models.CharField(max_length=32, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)  # a reservation that is not completed by then is released

    class Meta:
        db_table = "media_attachment"
        constraints = [
            # Lets other tables carry a composite foreign key (attachment_id, user_id): the owner is enforced by the database.
            models.UniqueConstraint(fields=["id", "user_id"], name="media_attachment_id_user_unique"),
            models.UniqueConstraint(fields=["bucket", "path"], name="media_attachment_object_unique"),
            models.CheckConstraint(condition=Q(bytes__gte=0), name="media_attachment_bytes_nonnegative"),
            models.CheckConstraint(
                condition=Q(status__in=["reserved", "uploaded", "clean", "rejected", "deleting"]),
                name="media_attachment_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["user_id", "kind"], name="media_att_owner_kind_idx"),
            models.Index(fields=["expires_at"], condition=Q(status="reserved"), name="media_att_reservation_idx"),
        ]

    @property
    def is_expired_reservation(self) -> bool:
        return self.status == self.Status.RESERVED and self.expires_at is not None and self.expires_at < timezone.now()
