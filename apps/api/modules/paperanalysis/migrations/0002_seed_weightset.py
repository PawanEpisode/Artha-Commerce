import uuid

from django.db import migrations

from modules.paperanalysis.domain.params import DEFAULT_PARAMS, ENGINE_VERSION


def seed_global_weightset(apps, schema_editor):
    WeightSet = apps.get_model("paperanalysis", "WeightSet")
    WeightSet.objects.get_or_create(
        name="Global ps-1 defaults",
        engine_version=ENGINE_VERSION,
        scope_course=None,
        scope_level=None,
        defaults={
            "id": uuid.uuid4(),
            "params": DEFAULT_PARAMS,
            "params_schema": 1,
            "status": "active",
            "notes": "Initial heuristics, not yet back-tested",
        },
    )


def remove_global_weightset(apps, schema_editor):
    WeightSet = apps.get_model("paperanalysis", "WeightSet")
    WeightSet.objects.filter(
        name="Global ps-1 defaults",
        engine_version=ENGINE_VERSION,
        scope_course=None,
        scope_level=None,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("paperanalysis", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_global_weightset, remove_global_weightset),
    ]
