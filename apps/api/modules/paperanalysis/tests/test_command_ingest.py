"""
Tests for ingest_analysis_papers management command.
"""

from __future__ import annotations

import tempfile
from io import StringIO

import pytest
from django.core.management import call_command

from modules.paperanalysis.models import Allocation, Paper, PaperQuestion


@pytest.mark.django_db
def test_skeleton_csv_dry_run_and_publish(syllabus_tree):
    # CSV content targeting taxation subject
    csv_content = """label,position,marks,format,nature,section,choice_group,pick_n,of_m,chapter_key,topic_key,share,source_ref,tag_hint
1,1,10.0,descriptive,practical,Section A,,,,gst-itc,,1.0,pyq:tax:2024,
2,2,10.0,descriptive,theory,Section A,,,,residential-status,,1.0,pyq:tax:2024,
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".csv") as tmp:
        tmp.write(csv_content)
        tmp.flush()

        out = StringIO()
        # 1. Dry run
        call_command(
            "ingest_analysis_papers",
            "--skeleton-csv",
            tmp.name,
            "--subject",
            "taxation",
            "--term-code",
            "2024-06",
            "--total-marks",
            "20.0",
            "--dry-run",
            stdout=out,
        )
        assert "Parsed 2 rows" in out.getvalue()
        assert not Paper.objects.filter(subject_key="taxation", term_code="2024-06").exists()

        # 2. Real run with publish
        out2 = StringIO()
        call_command(
            "ingest_analysis_papers",
            "--skeleton-csv",
            tmp.name,
            "--subject",
            "taxation",
            "--term-code",
            "2024-06",
            "--total-marks",
            "20.0",
            "--publish",
            stdout=out2,
        )
        paper = Paper.objects.get(subject_key="taxation", term_code="2024-06")
        assert paper.status == Paper.Status.PUBLISHED
        assert paper.confirmed_marks == 20.0
        assert PaperQuestion.objects.filter(paper=paper).count() == 2
        assert Allocation.objects.filter(paper_question__paper=paper).count() == 2


@pytest.mark.django_db
def test_filter_no_match(syllabus_tree):
    out = StringIO()
    call_command(
        "ingest_analysis_papers",
        "--paper",
        "9999",
        stdout=out,
    )
    assert "No seed files matched" in out.getvalue()
