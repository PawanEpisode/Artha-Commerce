"""
Tests for mocktest seed_mocktests management command.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from django.core.management import call_command

from modules.mocktest.models import Paper, PaperVersion, Section, Item
from modules.syllabus.tests.helpers import make_scheme


@pytest.mark.django_db
def test_seed_mocktests_command(tmp_path):
    scheme = make_scheme()
    level = scheme.level
    course = level.course
    subject = scheme.subjects.first()
    chapter = subject.chapters.first()

    seed_file = tmp_path / "test-paper.json"
    paper_data = {
        "course_code": course.code,
        "level_code": level.code,
        "scheme_code": scheme.code,
        "subject_key": subject.key,
        "title": "CA Final Audit Mock 1",
        "slug": "ca-final-audit-mock-1",
        "total_marks": 100,
        "duration_minutes": 180,
        "sections": [
          {
            "key": "A",
            "title": "MCQ Section",
            "kind": "objective",
            "marks_total": 30,
            "items": [
              {
                "position": 1,
                "display_label": "Q.1",
                "marks": 2,
                "question": {
                  "external_ref": "mock:test:q1",
                  "kind": "mcq_single",
                  "stem_md": "Which standard applies?",
                  "options": [
                    {"body_md": "SA 200", "is_correct": True},
                    {"body_md": "SA 500", "is_correct": False}
                  ],
                  "chapter_key": chapter.key
                }
              }
            ]
          }
        ]
    }
    seed_file.write_text(json.dumps(paper_data), encoding="utf-8")

    # Run command
    call_command("seed_mocktests", file=str(seed_file), publish=True)

    paper = Paper.objects.filter(slug="ca-final-audit-mock-1").first()
    assert paper is not None
    assert paper.status == Paper.Status.LIVE
    assert paper.visibility == Paper.Visibility.PUBLIC
    assert paper.versions.count() == 1

    version = paper.versions.first()
    assert version.sections.count() == 1
    assert version.items.count() == 1
    item = version.items.first()
    assert item.display_label == "Q.1"
    assert item.marks == 2
