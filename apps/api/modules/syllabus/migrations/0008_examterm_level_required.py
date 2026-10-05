"""Exam terms per level (final step): `level` is required and the code is unique inside a level."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("syllabus", "0007_examterm_per_level_data")]

    operations = [
        migrations.AlterField(
            model_name="examterm",
            name="level",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="terms", to="syllabus.level"
            ),
        ),
        migrations.AlterField(
            model_name="examterm",
            name="course",
            field=models.ForeignKey(
                editable=False, on_delete=django.db.models.deletion.PROTECT, related_name="terms", to="syllabus.course"
            ),
        ),
        migrations.AddConstraint(
            model_name="examterm",
            constraint=models.UniqueConstraint(fields=("level", "code"), name="syllabus_examterm_unique_level_code"),
        ),
    ]
