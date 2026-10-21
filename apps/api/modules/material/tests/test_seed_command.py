"""
Tests for material seed_study_material management command.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from django.core.management import call_command

from modules.material.models import Edition, EditionItem, Item, Provider, Work
from modules.syllabus.tests.helpers import make_scheme


@pytest.mark.django_db
def test_seed_study_material_command(tmp_path):
    scheme = make_scheme()
    level = scheme.level
    course = level.course
    subject = scheme.subjects.first()
    chapter = subject.chapters.first()

    seed_file = tmp_path / "test-material.json"
    material_data = {
        "provider": "icai",
        "provider_name": "Institute of Chartered Accountants of India",
        "course_code": course.code,
        "level_code": level.code,
        "subject_key": subject.key,
        "work_key": "ca-final-audit-module-1",
        "title": "CA Final Audit Study Material",
        "edition": {
            "label": "2024 Edition",
            "applies_from_term": "2024-05",
            "page_offset": 10
        },
        "units": [
            {
                "unit_key": "unit-01",
                "title": "Chapter 1 Audit Strategy",
                "chapter_key": chapter.key,
                "items": [
                    {
                        "item_key": "unit-01-ill-1",
                        "printed_label": "Illustration 1",
                        "kind": "illustration",
                        "printed_page": 5,
                        "descriptor": "Audit Risk evaluation"
                    }
                ]
            }
        ]
    }
    seed_file.write_text(json.dumps(material_data), encoding="utf-8")

    # Run command
    call_command("seed_study_material", file=str(seed_file), publish=True)

    work = Work.objects.filter(work_key="ca-final-audit-module-1").first()
    assert work is not None
    assert work.provider.slug == "icai"
    assert work.editions.count() == 1

    edition = work.editions.first()
    assert edition.status == Edition.Status.CURRENT
    assert edition.units.count() == 1
    assert edition.items.count() == 1

    ed_item = edition.items.first()
    assert ed_item.printed_label == "Illustration 1"
    assert ed_item.chapter_key == chapter.key
