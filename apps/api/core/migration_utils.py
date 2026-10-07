"""
PostgreSQL-only DDL for migrations that must also run on SQLite (the quick test database).

Django cannot declare composite foreign keys, exclusion constraints or `btree_gin` indexes, so migrations add them with
raw SQL. Each helper returns a `RunPython` that executes only when the connection is PostgreSQL and is reversible, so
`makemigrations --check` stays clean (the model state never mentions them) and SQLite keeps the service-level checks.

    operations = [postgres_only(*composite_fk("notes_noteversion", "notes_noteversion_note_user_fk", ...))]
"""

from __future__ import annotations

from collections.abc import Iterable

from django.db import migrations


def postgres_only(forward: Iterable[str], reverse: Iterable[str] = ()) -> migrations.RunPython:
    """Runs `forward` statements on PostgreSQL (nothing elsewhere); `reverse` undoes them. No statement may contain `%`."""
    forward, reverse = list(forward), list(reverse)

    def run(statements):
        def apply(apps, schema_editor):
            if schema_editor.connection.vendor != "postgresql":
                return
            for sql in statements:
                schema_editor.execute(sql)

        return apply

    return migrations.RunPython(run(forward), run(reverse))


def composite_fk(
    table: str,
    name: str,
    columns: tuple[str, ...],
    ref_table: str,
    ref_columns: tuple[str, ...],
    *,
    on_delete: str = "CASCADE",
) -> tuple[list[str], list[str]]:
    """
    A foreign key over `(parent_id, user_id)`: the owner of the child equals the owner of the parent, enforced by the
    database. Added `NOT VALID` then validated, so a large table is only briefly locked and existing rows are checked.
    Not deferrable: a cross-student link fails at the statement that writes it. A NULL in any column skips the check
    (MATCH SIMPLE), which is how the nullable `note_id`, `annotation_id` and `document_id` of `notes_itemtag` work.
    """
    cols, refs = ", ".join(columns), ", ".join(ref_columns)
    forward = [
        f"ALTER TABLE {table} ADD CONSTRAINT {name} FOREIGN KEY ({cols}) REFERENCES {ref_table} ({refs}) "
        f"ON DELETE {on_delete} NOT VALID",
        f"ALTER TABLE {table} VALIDATE CONSTRAINT {name}",
    ]
    return forward, [f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"]


def composite_fks(*specs: tuple) -> migrations.RunPython:
    """One `RunPython` for several `composite_fk(...)` argument tuples."""
    forward: list[str] = []
    reverse: list[str] = []
    for spec in specs:
        f, r = composite_fk(*spec)
        forward += f
        reverse = r + reverse
    return postgres_only(forward, reverse)
