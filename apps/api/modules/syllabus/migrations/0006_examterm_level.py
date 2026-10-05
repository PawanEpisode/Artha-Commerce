"""Exam terms become per level (schema step): add `level`, drop the per-course unique code."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("syllabus", "0005_seed_ca_spom_level")]

    operations = [
        migrations.RemoveConstraint(model_name="examterm", name="syllabus_examterm_unique_code"),
        migrations.AddField(
            model_name="examterm",
            name="level",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.PROTECT, related_name="terms", to="syllabus.level"
            ),
        ),
    ]
