"""
Integration tests for PYQ services (paper import, publish, and session launch).
"""

from __future__ import annotations

import uuid

import pytest

from modules.pyq.models import PyqPaper
from modules.pyq.services import import_paper, publish_paper, start_chapter_session, start_paper_session


@pytest.fixture
def sample_paper_payload(syllabus_tree):
    scheme = syllabus_tree
    level = scheme.level
    course = level.course
    subject = scheme.subjects.first()
    chapter = subject.chapters.first()

    return {
        "external_ref": "pyq:cma:inter:taxation:2024-06",
        "course_code": course.code,
        "level_code": level.code,
        "subject_key": subject.key,
        "term_code": "2024-06",
        "title": "CMA Intermediate June 2024 Paper 7: Direct & Indirect Taxation",
        "paper_code": "Paper 7",
        "duration_minutes": 180,
        "reading_minutes": 15,
        "total_marks": 20.0,
        "delivery": "link_out",
        "source_name": "ICMAI",
        "links": [
            {
                "link_kind": "paper",
                "label": "Official QP",
                "url": "https://icmai.in/upload/Students/Question_Papers/Inter_June2024.pdf",
            }
        ],
        "choice_groups": [
            {
                "ref": "cg1",
                "label": "Compulsory Section A",
                "rule_kind": "compulsory",
                "pick_count": 1,
                "of_count": 1,
            }
        ],
        "parts": [
            {
                "ref": "q1",
                "number_label": "1",
                "depth": 0,
                "sort_order": 1,
                "is_leaf": False,
                "marks": 20.0,
                "choice_group_ref": "cg1",
            },
            {
                "ref": "q1a",
                "parent_ref": "q1",
                "number_label": "1(a)",
                "depth": 1,
                "sort_order": 2,
                "is_leaf": True,
                "marks": 10.0,
                "kind": "long_form",
                "descriptor": "Compute total income from salaries",
                "chapter_key": chapter.key,
                "answer_source": "icmai_suggested",
            },
            {
                "ref": "q1b",
                "parent_ref": "q1",
                "number_label": "1(b)",
                "depth": 1,
                "sort_order": 3,
                "is_leaf": True,
                "marks": 10.0,
                "kind": "long_form",
                "descriptor": "Deductions under chapter VI-A",
                "chapter_key": chapter.key,
                "answer_source": "icmai_suggested",
            },
        ],
    }


@pytest.mark.django_db
def test_import_paper_dry_run_and_commit(sample_paper_payload):
    editor_id = uuid.uuid4()

    # Dry run
    report_dry = import_paper(editor_id, sample_paper_payload, dry_run=True)
    assert report_dry.is_valid is True
    assert report_dry.paper is None
    assert PyqPaper.objects.count() == 0

    # Real import
    report = import_paper(editor_id, sample_paper_payload, dry_run=False)
    assert report.is_valid is True
    assert report.paper is not None
    assert report.created_questions == 2

    paper = PyqPaper.objects.get(external_ref="pyq:cma:inter:taxation:2024-06")
    assert paper.question_count == 2
    assert paper.questions.count() == 3  # 1 interior + 2 leaf
    assert paper.links.count() == 1
    assert paper.choice_groups.count() == 1

    # Verify underlying questionbank items were created
    leaf_pqs = paper.questions.filter(is_leaf=True)
    for pq in leaf_pqs:
        assert pq.question is not None
        assert pq.question.source_kind == "institute_pyq"
        assert pq.question.live_version is not None


@pytest.mark.django_db
def test_publish_paper_and_launch_sessions(sample_paper_payload):
    editor_id = uuid.uuid4()
    user_id = uuid.uuid4()

    report = import_paper(editor_id, sample_paper_payload)
    paper = report.paper

    # Publish paper
    pub_paper = publish_paper(editor_id, paper.id)
    assert pub_paper.status == PyqPaper.Status.PUBLISHED
    assert pub_paper.published_at is not None

    # Launch paper session
    session_res = start_paper_session(user_id, paper.id, mode="timed")
    assert session_res["question_count"] == 2
    assert session_res["mode"] == "timed"
    assert session_res["status"] == "created"

    # Launch chapter session
    chapter = paper.questions.filter(is_leaf=True).first().chapter
    assert chapter is not None
    ch_session_res = start_chapter_session(user_id, chapter.id, count=5)
    assert ch_session_res["question_count"] == 2
    assert ch_session_res["mode"] == "chapter_quiz"
