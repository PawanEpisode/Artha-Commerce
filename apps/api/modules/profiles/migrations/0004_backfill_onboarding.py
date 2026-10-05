from django.db import migrations
from django.utils import timezone

BATCH = 1000
BACKFILLED_VERSION = 1  # what existing students had already finished: course, date and hours (F-02 onboarding)


def backfill(apps, schema_editor):
    """
    Students who already have an active enrolment completed the old onboarding. Mark them version 1 so the new flow
    shows them only what is new (`update` mode) instead of starting them over. Idempotent: rows that exist are kept.
    """
    Profile = apps.get_model("profiles", "Profile")
    Onboarding = apps.get_model("profiles", "Onboarding")
    Enrollment = apps.get_model("coverage", "Enrollment")

    enrolled = set(Enrollment.objects.filter(status="active").values_list("user_id", flat=True).distinct())
    existing = set(Onboarding.objects.values_list("user_id", flat=True))
    pending = [pk for pk in Profile.objects.filter(pk__in=enrolled).values_list("pk", flat=True) if pk not in existing]

    now = timezone.now()
    for start in range(0, len(pending), BATCH):
        Onboarding.objects.bulk_create(
            [
                Onboarding(
                    user_id=pk,
                    completed_version=BACKFILLED_VERSION,
                    backfilled=True,
                    started_at=now,
                    completed_at=now,
                )
                for pk in pending[start : start + BATCH]
            ],
            ignore_conflicts=True,
        )


def unbackfill(apps, schema_editor):
    Onboarding = apps.get_model("profiles", "Onboarding")
    Onboarding.objects.filter(backfilled=True, completed_version=BACKFILLED_VERSION).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0003_profile_personalization"),
        ("coverage", "0004_study_targets_and_daily_minutes"),
    ]

    operations = [migrations.RunPython(backfill, unbackfill)]
