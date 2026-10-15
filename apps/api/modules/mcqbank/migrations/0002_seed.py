"""
Migration to seed system presets and draft reference sources (F-05 ERD section 4).
"""

from __future__ import annotations

import uuid

from django.db import migrations


def seed_mcq_data(apps, schema_editor):
    TestPreset = apps.get_model("mcqbank", "TestPreset")
    RefSource = apps.get_model("mcqbank", "RefSource")

    # System presets
    system_presets = [
        {
            "id": uuid.UUID("f0500000-0000-4000-a000-000000000001"),
            "name": "Quick 10",
            "is_system": True,
            "kind": "blueprint",
            "mode": "chapter_quiz",
            "picker": "mcq_blueprint",
            "spec": {"v": 1, "count": 10, "mix": "smart"},
            "sort_order": 1,
        },
        {
            "id": uuid.UUID("f0500000-0000-4000-a000-000000000002"),
            "name": "Timed 20",
            "is_system": True,
            "kind": "builder",
            "mode": "timed",
            "picker": "filter",
            "spec": {"v": 1, "count": 20, "order": "random", "filter": {"kind_groups": ["choice"]}},
            "time_limit_seconds": 1800,  # 30 mins
            "sort_order": 2,
        },
        {
            "id": uuid.UUID("f0500000-0000-4000-a000-000000000003"),
            "name": "Revise Wrong",
            "is_system": True,
            "kind": "builder",
            "mode": "revision",
            "picker": "wrong_only",
            "spec": {"v": 1, "count": 10, "order": "random"},
            "sort_order": 3,
        },
        {
            "id": uuid.UUID("f0500000-0000-4000-a000-000000000004"),
            "name": "Bookmarked",
            "is_system": True,
            "kind": "builder",
            "mode": "revision",
            "picker": "filter",
            "spec": {"v": 1, "count": 10, "filter": {"personal": "bookmarked", "kind_groups": ["choice"]}},
            "sort_order": 4,
        },
    ]

    for p in system_presets:
        TestPreset.objects.update_or_create(
            id=p["id"],
            defaults=p,
        )

    # Draft reference sources
    ref_sources = [
        {"prefix": "cgst", "label": "CGST Act, 2017", "url_kind": "bare_act"},
        {"prefix": "igst", "label": "IGST Act, 2017", "url_kind": "bare_act"},
        {"prefix": "indas", "label": "Indian Accounting Standards (Ind AS)", "url_kind": "standard"},
        {"prefix": "sa", "label": "Standards on Auditing (SA)", "url_kind": "standard"},
        {"prefix": "as", "label": "Accounting Standards (AS)", "url_kind": "standard"},
        {"prefix": "companiesact", "label": "Companies Act, 2013", "url_kind": "bare_act"},
    ]

    for r in ref_sources:
        RefSource.objects.update_or_create(
            prefix=r["prefix"],
            defaults={
                "label": r["label"],
                "url_kind": r["url_kind"],
                "url_template": "",
                "status": "draft",
            },
        )


def rollback_mcq_data(apps, schema_editor):
    TestPreset = apps.get_model("mcqbank", "TestPreset")
    RefSource = apps.get_model("mcqbank", "RefSource")

    TestPreset.objects.filter(is_system=True).delete()
    RefSource.objects.filter(prefix__in=["cgst", "igst", "indas", "sa", "as", "companiesact"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("mcqbank", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_mcq_data, rollback_mcq_data),
    ]
