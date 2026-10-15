"""
API view tests for PYQ module (fail closed, paper listing, details, session launch, editor endpoints).
"""

from __future__ import annotations

import uuid

import pytest

from modules.pyq.services import import_paper, publish_paper


@pytest.fixture
def published_paper(syllabus_tree):
    scheme = syllabus_tree
    level = scheme.level
    course = level.course
    subject = scheme.subjects.first()
    chapter = subject.chapters.first()
    editor_id = uuid.uuid4()

    payload = {
        "external_ref": "pyq:cma:inter:taxation:2024-06",
        "course_code": course.code,
        "level_code": level.code,
        "subject_key": subject.key,
        "term_code": "2024-06",
        "title": "CMA Intermediate June 2024 Paper 7",
        "paper_code": "Paper 7",
        "total_marks": 10.0,
        "delivery": "link_out",
        "links": [
            {
                "link_kind": "paper",
                "label": "QP",
                "url": "https://icmai.in/paper.pdf",
            }
        ],
        "parts": [
            {
                "ref": "q1",
                "number_label": "1",
                "depth": 0,
                "sort_order": 1,
                "is_leaf": True,
                "marks": 10.0,
                "kind": "long_form",
                "descriptor": "Tax computation",
                "chapter_key": chapter.key,
            }
        ],
    }
    report = import_paper(editor_id, payload)
    return publish_paper(editor_id, report.paper.id)


@pytest.mark.django_db
def test_flags_fail_closed(api, pyq_flags, published_paper):
    # Disable pyq_bank
    pyq_flags(False)
    res = api.get("/pyq/papers/")
    assert res.status_code == 403


@pytest.mark.django_db
def test_papers_list_and_detail(api, published_paper):
    res = api.get("/pyq/papers/")
    assert res.status_code == 200
    assert len(res.json_body["items"]) == 1
    assert res.json_body["items"][0]["external_ref"] == published_paper.external_ref

    detail_res = api.get(f"/pyq/papers/{published_paper.id}/")
    assert detail_res.status_code == 200
    body = detail_res.json_body
    assert body["title"] == published_paper.title
    assert len(body["questions"]) == 1
    assert len(body["links"]) == 1
    assert body["questions"][0]["number_label"] == "1"


@pytest.mark.django_db
def test_paper_practice_start(api, published_paper):
    res = api.post(f"/pyq/papers/{published_paper.id}/practice/", {"mode": "untimed"})
    assert res.status_code == 201
    assert "session_id" in res.json_body
    assert res.json_body["question_count"] == 1


@pytest.mark.django_db
def test_chapter_pyqs_and_practice(api, published_paper):
    chapter = published_paper.questions.first().chapter
    assert chapter is not None

    res = api.get(f"/pyq/chapters/{chapter.id}/")
    assert res.status_code == 200
    assert len(res.json_body["items"]) == 1

    start_res = api.post(f"/pyq/chapters/{chapter.id}/practice/", {"count": 5})
    assert start_res.status_code == 201
    assert "session_id" in start_res.json_body


@pytest.mark.django_db
def test_editor_import_and_publish_endpoints(editor_api, syllabus_tree):
    scheme = syllabus_tree
    level = scheme.level
    course = level.course
    subject = scheme.subjects.first()
    chapter = subject.chapters.first()

    payload = {
        "external_ref": "pyq:cma:final:cost-audit:2024-12",
        "course_code": course.code,
        "level_code": level.code,
        "subject_key": subject.key,
        "term_code": "2024-12",
        "title": "CMA Final Dec 2024 Cost Audit",
        "total_marks": 10.0,
        "delivery": "link_out",
        "parts": [
            {
                "number_label": "1",
                "depth": 0,
                "sort_order": 1,
                "is_leaf": True,
                "marks": 10.0,
                "chapter_key": chapter.key,
            }
        ],
    }

    # Import
    imp_res = editor_api.post("/pyq/editor/import-paper/", {"payload": payload})
    assert imp_res.status_code == 201
    paper_id = imp_res.json_body["paper_id"]

    # Publish
    pub_res = editor_api.post(f"/pyq/editor/papers/{paper_id}/publish/")
    assert pub_res.status_code == 200
    assert pub_res.json_body["status"] == "published"
