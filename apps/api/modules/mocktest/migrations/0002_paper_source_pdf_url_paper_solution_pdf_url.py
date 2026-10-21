# Generated migration for Paper source_pdf_url and solution_pdf_url

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mocktest', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='paper',
            name='source_pdf_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='paper',
            name='solution_pdf_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
    ]
