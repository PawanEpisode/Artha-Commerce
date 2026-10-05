"""
The student: identity (name, avatar), onboarding progress and the last visited page (PRD/ERD F-16).
`user_id` columns reference `auth.users.id` by value (no cross-schema foreign key), like every other module.
Coverage, tracking and focus data stay with their own modules; this app only reads them through their selectors.
"""

import uuid

from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


def default_onboarding_steps() -> dict:
    """`v` is the schema version of this document; `items` holds only steps that are not derived from facts."""
    return {"v": 1, "items": {}}


class Profile(TimeStampedModel):
    """One row per Supabase auth user. `id` equals auth.users.id, so there is no join table."""

    class Course(models.TextChoices):
        CA = "ca", "Chartered Accountancy"
        CS = "cs", "Company Secretaryship"
        CMA = "cma", "Cost and Management Accountancy"

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        EDITOR = "editor", "Editor"
        ADMIN = "admin", "Admin"

    class AvatarKind(models.TextChoices):
        INITIALS = "initials", "Initials"
        PRESET = "preset", "Preset"
        UPLOAD = "upload", "Upload"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(blank=True)
    # The service enforces 1 to 60 characters after trim and NFC (`domain.names`); legacy longer values are left alone.
    full_name = models.CharField(max_length=120, blank=True)
    avatar_kind = models.CharField(max_length=8, choices=AvatarKind.choices, default=AvatarKind.INITIALS)
    avatar_preset_key = models.CharField(max_length=24, blank=True, default="")  # p01..p24, only for kind preset
    avatar_key = models.CharField(max_length=120, blank=True, default="")  # object key stem, only for kind upload
    avatar_version = models.IntegerField(default=0)  # +1 on every avatar change; part of the web query key
    avatar_updated_at = models.DateTimeField(null=True, blank=True)
    # Deprecated: the provider image URL copied from the JWT claims. Not served; the source for "Use my Google photo" (R3).
    avatar_url = models.URLField(blank=True)
    # Deprecated: no reader and no writer since F-16. The course is the active coverage enrolment. Dropped later.
    course = models.CharField(max_length=8, choices=Course.choices, blank=True)
    level = models.CharField(max_length=32, blank=True)
    exam_date = models.DateField(null=True, blank=True)
    # Staff roles are granted by an admin in the database, never through the API (the serializer does not expose it).
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)

    class Meta:
        db_table = "profiles"
        constraints = [
            models.CheckConstraint(
                condition=Q(avatar_kind__in=["initials", "preset", "upload"]), name="profiles_avatar_kind_valid"
            ),
            models.CheckConstraint(
                condition=(
                    Q(avatar_kind="initials", avatar_preset_key="", avatar_key="")
                    | Q(avatar_kind="preset", avatar_key="") & ~Q(avatar_preset_key="")
                    | Q(avatar_kind="upload", avatar_preset_key="") & ~Q(avatar_key="")
                ),
                name="profiles_avatar_shape",
            ),
        ]

    def __str__(self) -> str:
        return self.email or str(self.id)


class Onboarding(TimeStampedModel):
    """
    One row per student, created lazily on the first `GET /me/`. Stores only order, skipped optional steps and
    timestamps: whether a step is done is read from the owning table (facts over flags), so a stale flag can never mark
    someone complete with missing data.
    """

    user_id = models.UUIDField(primary_key=True)
    completed_version = models.SmallIntegerField(default=0)  # highest ONBOARDING_VERSION completed, 0 = never
    backfilled = models.BooleanField(default=False)  # set by the migration, so analytics and support can tell
    current_step = models.CharField(max_length=24, blank=True, default="")  # resume hint only, never trusted
    steps = models.JSONField(default=default_onboarding_steps)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "profiles_onboarding"
        constraints = [
            models.CheckConstraint(
                condition=Q(completed_version__gte=0, completed_version__lte=100),
                name="profiles_onboarding_version_range",
            ),
            models.CheckConstraint(
                condition=(Q(completed_at__isnull=True, completed_version=0))
                | (Q(completed_at__isnull=False, completed_version__gt=0)),
                name="profiles_onboarding_completed_pair",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} v{self.completed_version}"


class LastVisit(models.Model):
    """
    The page the student last used, written only when the tab is hidden (never on navigation). A separate narrow
    table so the timer-less write never rewrites the wide `profiles` row; one row per student, updated in place.
    """

    user_id = models.UUIDField(primary_key=True)
    path = models.CharField(max_length=300)  # pathname only, validated against the restorable allow-list
    search = models.CharField(max_length=200, blank=True, default="")
    visited_at = models.DateTimeField()

    class Meta:
        db_table = "profiles_lastvisit"
        constraints = [models.CheckConstraint(condition=Q(path__startswith="/app"), name="profiles_lastvisit_path_app")]

    def __str__(self) -> str:
        return f"{self.user_id} {self.path}"


class StorageDelete(models.Model):
    """Outbox for file deletions that failed or need cleanup. `sweep_avatars` retries them daily, then removes the row."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField()
    bucket = models.CharField(max_length=40, default="avatars")
    path = models.CharField(max_length=200)
    attempts = models.SmallIntegerField(default=0)  # gives up and alerts after 8
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "profiles_storagedelete"
        constraints = [models.UniqueConstraint(fields=["bucket", "path"], name="profiles_storagedelete_unique")]
        indexes = [models.Index(fields=["created_at"], name="profiles_sd_created_idx")]

    def __str__(self) -> str:
        return f"{self.bucket}/{self.path}"
