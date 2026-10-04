import uuid

from django.db import models

from core.models import TimeStampedModel


class Profile(TimeStampedModel):
    """One row per Supabase auth user. `id` equals auth.users.id, so there is no join table."""

    class Course(models.TextChoices):
        CA = "ca", "Chartered Accountancy"
        CS = "cs", "Company Secretaryship"
        CMA = "cma", "Cost and Management Accountancy"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(blank=True)
    full_name = models.CharField(max_length=120, blank=True)
    avatar_url = models.URLField(blank=True)
    course = models.CharField(max_length=8, choices=Course.choices, blank=True)
    level = models.CharField(max_length=32, blank=True)
    exam_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "profiles"

    def __str__(self) -> str:
        return self.email or str(self.id)
