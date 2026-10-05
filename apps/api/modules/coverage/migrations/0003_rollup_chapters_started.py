from django.db import migrations, models


def backfill_started(apps, schema_editor):
    """Existing roll-ups get their `chapters_started` now, so no student sees a stale 0 until the next write."""
    Rollup = apps.get_model("coverage", "Rollup")
    ChapterProgress = apps.get_model("coverage", "ChapterProgress")
    for row in Rollup.objects.all().iterator():
        started = ChapterProgress.objects.filter(enrollment_id=row.enrollment_id, is_excluded=False, coverage_pct__gt=0)
        if row.node_type == "subject":
            started = started.filter(chapter__subject_id=row.node_id)
        elif row.node_type == "group":
            started = started.filter(chapter__subject__group_id=row.node_id)
        count = started.count()
        if count:
            Rollup.objects.filter(enrollment_id=row.enrollment_id, node_type=row.node_type, node_id=row.node_id).update(
                chapters_started=count
            )


class Migration(migrations.Migration):
    dependencies = [("coverage", "0002_enrollment_elective")]

    operations = [
        migrations.AddField(
            model_name="rollup",
            name="chapters_started",
            field=models.SmallIntegerField(default=0),
        ),
        migrations.RunPython(backfill_started, migrations.RunPython.noop),
    ]
