from django.db import migrations, models


def backfill_daily_minutes(apps, schema_editor):
    """`daily_minutes = round(daily_hours * 60)` for every enrolment that has the legacy decimal hours."""
    Enrollment = apps.get_model("coverage", "Enrollment")
    for row in Enrollment.objects.filter(daily_hours__isnull=False, daily_minutes__isnull=True).iterator():
        minutes = round(float(row.daily_hours) * 60)
        Enrollment.objects.filter(pk=row.pk).update(daily_minutes=min(max(minutes, 15), 960))


class Migration(migrations.Migration):
    """
    F-16 S2. Expand step only: every default equals today's behaviour (targets 1, 2, 1), so no percentage moves.
    Reversible: the columns and constraints drop cleanly and the backfill is a no-op in reverse.
    """

    dependencies = [("coverage", "0003_rollup_chapters_started")]

    operations = [
        migrations.AddField(
            model_name="coveragesettings", name="target_practice_sets", field=models.SmallIntegerField(default=1)
        ),
        migrations.AddField(
            model_name="coveragesettings", name="target_revisions", field=models.SmallIntegerField(default=2)
        ),
        migrations.AddField(
            model_name="coveragesettings", name="target_mocks", field=models.SmallIntegerField(default=1)
        ),
        migrations.AddField(
            model_name="coveragesettings",
            name="targets_preset",
            field=models.CharField(default="custom", max_length=10),
        ),
        migrations.AddField(
            model_name="coveragesettings", name="targets_version", field=models.IntegerField(default=1)
        ),
        migrations.AddField(
            model_name="coveragesettings",
            name="targets_confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="enrollment", name="daily_minutes", field=models.SmallIntegerField(blank=True, null=True)
        ),
        migrations.AddConstraint(
            model_name="coveragesettings",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("target_practice_sets__gte", 0),
                    ("target_practice_sets__lte", 10),
                    ("target_revisions__gte", 0),
                    ("target_revisions__lte", 10),
                    ("target_mocks__gte", 0),
                    ("target_mocks__lte", 10),
                ),
                name="coverage_settings_targets_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="coveragesettings",
            constraint=models.CheckConstraint(
                condition=models.Q(("targets_preset__in", ["light", "standard", "intense", "custom"])),
                name="coverage_settings_targets_preset_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="enrollment",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("daily_minutes__isnull", True),
                    models.Q(("daily_minutes__gte", 15), ("daily_minutes__lte", 960)),
                    _connector="OR",
                ),
                name="coverage_enrollment_minutes",
            ),
        ),
        migrations.RunPython(backfill_daily_minutes, migrations.RunPython.noop),
    ]
