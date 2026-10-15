"""Data migration to backfill live_version and current_version on Question."""

from django.db import migrations


def backfill_live_versions(apps, schema_editor):
    Question = apps.get_model("questionbank", "Question")
    QuestionVersion = apps.get_model("questionbank", "QuestionVersion")

    for q in Question.objects.filter(live_version__isnull=True):
        ver = (
            QuestionVersion.objects.filter(question_id=q.id, state="live").first()
            or QuestionVersion.objects.filter(question_id=q.id).order_by("-version_no").first()
        )
        if ver:
            q.live_version = ver
            q.current_version = ver
            q.save(update_fields=["live_version", "current_version"])


class Migration(migrations.Migration):
    dependencies = [
        ("questionbank", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_live_versions, reverse_code=migrations.RunPython.noop),
    ]
