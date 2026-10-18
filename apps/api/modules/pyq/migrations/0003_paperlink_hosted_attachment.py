from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pyq", "0002_alter_askedcache_last_term_code_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="paperlink",
            name="attachment_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="paperlink",
            name="url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
        migrations.AddConstraint(
            model_name="paperlink",
            constraint=models.CheckConstraint(
                condition=models.Q(("url", ""), _negated=True) | models.Q(("attachment_id__isnull", False)),
                name="pyq_paperlink_url_or_attachment",
            ),
        ),
    ]
