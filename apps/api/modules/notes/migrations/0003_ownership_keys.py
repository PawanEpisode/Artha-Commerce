"""
Ownership hardening for the R1 tables: composite foreign keys `(parent_id, user_id)` so a child row can only ever point at
a parent of the same student (ERD 2.5, 2.8; audit AUD-001). PostgreSQL only; SQLite keeps the service-level checks. The
parents already carry unique `(id, user_id)` (Tag, Note, media Attachment), so nothing else is needed here.
"""

from django.db import migrations

from core.migration_utils import composite_fks

TAG = ("notes_tag", ("id", "user_id"))
NOTE = ("notes_note", ("id", "user_id"))
ATTACHMENT = ("media_attachment", ("id", "user_id"))


class Migration(migrations.Migration):
    dependencies = [
        ("media", "0001_initial"),
        ("notes", "0002_seed_free_plan"),
    ]

    operations = [
        composite_fks(
            ("notes_itemtag", "notes_itemtag_tag_user_fk", ("tag_id", "user_id"), *TAG),
            ("notes_itemtag", "notes_itemtag_note_user_fk", ("note_id", "user_id"), *NOTE),
            ("notes_noteimage", "notes_noteimage_note_user_fk", ("note_id", "user_id"), *NOTE),
            ("notes_noteimage", "notes_noteimage_attachment_user_fk", ("attachment_id", "user_id"), *ATTACHMENT),
            ("notes_noteversion", "notes_noteversion_note_user_fk", ("note_id", "user_id"), *NOTE),
        ),
    ]
