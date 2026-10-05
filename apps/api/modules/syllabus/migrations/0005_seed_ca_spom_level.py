"""CA Self-Paced Online Modules (SPOM): ICAI's post-qualification modules, offered as their own level of the CA course."""

from django.db import migrations


def add_level(apps, schema_editor):
    Course = apps.get_model("syllabus", "Course")
    Level = apps.get_model("syllabus", "Level")
    course = Course.objects.filter(code="ca").first()
    if course is None:  # courses are created by 0002; nothing to attach to in a bare database
        return
    sort_order = Level.objects.filter(course=course).count()
    Level.objects.update_or_create(
        course=course,
        code="spom",
        defaults={"name": "Self-Paced Online Modules", "sort_order": sort_order, "is_active": True},
    )


class Migration(migrations.Migration):
    dependencies = [("syllabus", "0004_chapter_section_subject_source_url")]
    operations = [migrations.RunPython(add_level, migrations.RunPython.noop)]
