"""
Seed default readiness profiles for CA, CS, and CMA (F-10 ERD section 4).
"""

from datetime import date
from decimal import Decimal
import uuid
from django.db import migrations


def seed_profiles(apps, schema_editor):
    ReadinessProfile = apps.get_model("analytics", "ReadinessProfile")
    Course = apps.get_model("syllabus", "Course")

    courses = Course.objects.all()
    for course in courses:
        if not ReadinessProfile.objects.filter(course=course, version=1).exists():
            ReadinessProfile.objects.create(
                id=uuid.uuid4(),
                course=course,
                level=None,
                version=1,
                status="active",
                effective_from=date(2026, 10, 1),
                w_accuracy=Decimal("0.400"),
                w_breadth=Decimal("0.150"),
                w_coverage=Decimal("0.200"),
                w_retention=Decimal("0.150"),
                w_speed=Decimal("0.100"),
                half_life_days=45,
                lookback_factor=4,
                mode_weight_exam=Decimal("1.25"),
                repeat_weight=Decimal("0.50"),
                source_note="Default design values, [CALIBRATE] with tutors and beta data. Not Institute figures.",
            )


def reverse_seed(apps, schema_editor):
    ReadinessProfile = apps.get_model("analytics", "ReadinessProfile")
    ReadinessProfile.objects.filter(version=1, source_note__startswith="Default design values").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("analytics", "0001_initial"),
        ("syllabus", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_profiles, reverse_seed),
    ]
