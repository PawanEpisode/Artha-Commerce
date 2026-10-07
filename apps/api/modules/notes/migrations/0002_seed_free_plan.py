from django.db import migrations

FREE = {
    "max_storage_mb": 500,
    "max_file_mb": 50,
    "max_pages": 1000,
    "max_documents": 100,
    "max_notes": 2000,
    "max_note_chars": 100000,
    "max_note_images": 40,
    "max_marks_per_document": 20000,
    "max_tags": 200,
    "ocr_pages_per_month": 300,
    "ai_ocr_pages_per_month": 0,
    "ai_summaries_per_month": 5,
    "exports_per_month": 10,
    "max_share_links": 20,
    "max_offline_documents": 3,
}


def seed(apps, schema_editor):
    QuotaPlan = apps.get_model("notes", "QuotaPlan")
    QuotaPlan.objects.get_or_create(plan_code="free", defaults=FREE)


class Migration(migrations.Migration):
    dependencies = [("notes", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
