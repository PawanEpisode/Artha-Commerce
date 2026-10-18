"""
API view tests for MCQ Bank (F-05 ERD 7).
"""

from __future__ import annotations

import datetime
import uuid

import pytest

from modules.mcqbank.models import McqSet

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


@pytest.mark.django_db
def test_flags_fail_closed(api, mcq_flags):
    mcq_flags(False)
    res = api.get("/mcq/home/")
    assert res.status_code == 403


@pytest.mark.django_db
def test_home_view(api, syllabus_tree):
    res = api.get("/mcq/home/")
    assert res.status_code == 200
    assert "subjects" in res.json_body
    assert "course" in res.json_body


@pytest.mark.django_db
def test_home_view_enrolled_with_suggestions(api, syllabus_tree):
    from datetime import timedelta

    from django.utils import timezone

    from modules.coverage.services import create_enrollment
    from modules.mcqbank.tests.conftest import USER

    create_enrollment(
        USER,
        scheme_id=syllabus_tree.id,
        exam_date=(timezone.now() + timedelta(days=60)).date(),
        daily_minutes=120,
    )
    res = api.get("/mcq/home/")
    assert res.status_code == 200
    assert res.json_body["course"] == syllabus_tree.level.course.code
    assert res.json_body["level"] == syllabus_tree.level.code
    assert "suggestion" in res.json_body
    if res.json_body["suggestion"]:
        assert "chapter_id" in res.json_body["suggestion"]
        assert "subject_key" in res.json_body["suggestion"]


@pytest.mark.django_db
def test_subject_tiles(api, syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level
    subject = syllabus_tree.subjects.first()

    res = api.get(f"/mcq/subjects/{subject.key}/tiles/?course={course.code}&level={level.code}")
    assert res.status_code == 200
    assert isinstance(res.json_body, list)


@pytest.mark.django_db
def test_subject_tiles_default_to_the_students_enrolled_level(api, syllabus_tree):
    from datetime import timedelta

    from django.utils import timezone

    from modules.coverage.services import create_enrollment

    create_enrollment(
        USER,
        scheme_id=syllabus_tree.id,
        exam_date=(timezone.now() + timedelta(days=60)).date(),
        daily_minutes=120,
    )
    subject = syllabus_tree.subjects.first()
    res = api.get(f"/mcq/subjects/{subject.key}/tiles/")  # no ?course=&level=
    assert res.status_code == 200
    assert [t["chapter_key"] for t in res.json_body] == [c.key for c in subject.chapters.all()]


@pytest.mark.django_db
def test_chapter_detail_view(api, syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level
    subject = syllabus_tree.subjects.first()
    chapter = subject.chapters.first()

    res = api.get(f"/mcq/subjects/{subject.key}/chapters/{chapter.key}/?course={course.code}&level={level.code}")
    assert res.status_code == 200
    assert res.json_body["chapter_id"] == str(chapter.id)
    assert res.json_body["chapter_key"] == chapter.key
    assert "topics" in res.json_body
    assert "difficulty_split" in res.json_body


@pytest.mark.django_db
def test_sets_list_and_detail(api, syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level
    subject = syllabus_tree.subjects.first()

    s = McqSet.objects.create(
        slug="icmai-rtp-tax",
        title="ICMAI RTP Taxation",
        status=McqSet.Status.PUBLISHED,
        delivery=McqSet.Delivery.LINK_OUT,
        source_url="https://icmai.in/rtp",
        course=course,
        level=level,
        subject_key=subject.key,
        published_at=datetime.datetime.now(datetime.UTC),
    )

    res_list = api.get("/mcq/sets/")
    assert res_list.status_code == 200
    assert len(res_list.json_body["items"]) >= 1

    res_det = api.get(f"/mcq/sets/{s.slug}/")
    assert res_det.status_code == 200
    assert res_det.json_body["title"] == "ICMAI RTP Taxation"


@pytest.mark.django_db
def test_external_log_api(api, syllabus_tree):
    course = syllabus_tree.level.course
    level = syllabus_tree.level
    subject = syllabus_tree.subjects.first()
    chapter = subject.chapters.first()

    s = McqSet.objects.create(
        slug="cma-portal-mcq",
        title="CMA Portal MCQ",
        status=McqSet.Status.PUBLISHED,
        delivery=McqSet.Delivery.LINK_OUT,
        source_url="https://icmai.in/portal",
        course=course,
        level=level,
        subject_key=subject.key,
        chapter=chapter,
        published_at=datetime.datetime.now(datetime.UTC),
    )

    post_res = api.post(
        "/mcq/external-logs/",
        {
            "set_id": str(s.id),
            "score": "15.00",
            "max_score": "20.00",
            "taken_on": "2026-10-15",
            "client_id": str(uuid.uuid4()),
        },
    )
    assert post_res.status_code == 201
    assert post_res.json_body["score_pct"] == 75.0

    get_res = api.get("/mcq/external-logs/")
    assert get_res.status_code == 200
    assert len(get_res.json_body["items"]) == 1


@pytest.mark.django_db
def test_presets_api(api):
    post_res = api.post(
        "/mcq/presets/",
        {
            "name": "Evening Practice",
            "kind": "builder",
            "mode": "chapter_quiz",
            "picker": "filter",
            "spec": {"count": 10},
        },
    )
    assert post_res.status_code == 201

    get_res = api.get("/mcq/presets/")
    assert get_res.status_code == 200
    names = [p["name"] for p in get_res.json_body]
    assert "Evening Practice" in names
