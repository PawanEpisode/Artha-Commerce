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


@pytest.mark.django_db
def test_subject_tiles_count_only_the_chapters_own_choice_questions(api, syllabus_tree):
    """Regression: `chapter_id` and `kind_groups` used to be ignored, so every chapter showed the whole bank."""
    from modules.questionbank.models import Question

    course = syllabus_tree.level.course
    level = syllabus_tree.level
    subject = syllabus_tree.subjects.first()
    chapter = subject.chapters.first()

    def make(kind, chapter_obj):
        return Question.objects.create(
            kind=kind,
            stem_head="Q",
            visibility=Question.Visibility.PUBLIC,
            status=Question.Status.ACTIVE,
            course=course,
            level=level,
            primary_chapter=chapter_obj,
        )

    for _ in range(3):
        make("mcq_single", chapter)
    make("long_form", chapter)  # not a choice question
    make("mcq_single", None)  # belongs to no chapter

    res = api.get(f"/mcq/subjects/{subject.key}/tiles/?course={course.code}&level={level.code}")
    assert res.status_code == 200
    tile = next(t for t in res.json_body if t["chapter_id"] == str(chapter.id))
    assert tile["available"] == 3
    assert tile["unseen"] == 3


@pytest.mark.django_db
def test_quick_start_answers_the_new_session_id(api, syllabus_tree, monkeypatch):
    """Regression: the view read `session.id`, which the practice engine's SessionCreated does not have (HTTP 500)."""
    from decimal import Decimal

    from modules.practice import services as practice_services

    session_id = uuid.uuid4()
    monkeypatch.setattr(
        practice_services,
        "create_session",
        lambda **kwargs: practice_services.SessionCreated(
            session_id=session_id,
            question_count=10,
            title="",
            status="created",
            mode=kwargs["mode"],
            total_marks=Decimal("10"),
            time_limit_seconds=None,
            deadline_at=None,
        ),
    )
    chapter = syllabus_tree.subjects.first().chapters.first()

    res = api.post("/mcq/quick-start/", {"chapter_id": str(chapter.id), "count": 10, "mode": "chapter_quiz"})

    assert res.status_code == 201
    assert res.json_body == {"session_id": str(session_id)}


@pytest.mark.django_db
def test_quick_start_with_no_questions_is_a_clean_422(api, syllabus_tree):
    chapter = syllabus_tree.subjects.first().chapters.first()

    res = api.post("/mcq/quick-start/", {"chapter_id": str(chapter.id), "count": 10, "mode": "chapter_quiz"})

    assert res.status_code == 422
    assert res.json_body["error"]["code"] == "picker_empty"


def _stub_create_session(monkeypatch, seen: dict):
    from decimal import Decimal

    from modules.practice import services as practice_services

    def fake(**kwargs):
        seen.update(kwargs)
        return practice_services.SessionCreated(
            session_id=uuid.uuid4(),
            question_count=kwargs["spec"]["count"],
            title="",
            status="created",
            mode=kwargs["mode"],
            total_marks=Decimal("1"),
            time_limit_seconds=None,
            deadline_at=None,
        )

    monkeypatch.setattr(practice_services, "create_session", fake)


@pytest.mark.django_db
def test_quick_start_passes_the_chosen_feedback_policy_and_allows_a_hundred(api, syllabus_tree, monkeypatch):
    seen: dict = {}
    _stub_create_session(monkeypatch, seen)
    chapter = syllabus_tree.subjects.first().chapters.first()

    res = api.post(
        "/mcq/quick-start/",
        {"chapter_id": str(chapter.id), "count": 100, "mode": "chapter_quiz", "feedback_policy": "instant"},
    )

    assert res.status_code == 201
    assert seen["feedback_policy"] == "instant"
    assert seen["spec"]["count"] == 100


@pytest.mark.django_db
def test_quick_start_without_feedback_policy_leaves_it_to_the_mode(api, syllabus_tree, monkeypatch):
    seen: dict = {}
    _stub_create_session(monkeypatch, seen)
    chapter = syllabus_tree.subjects.first().chapters.first()

    res = api.post("/mcq/quick-start/", {"chapter_id": str(chapter.id), "count": 10})

    assert res.status_code == 201
    assert seen["feedback_policy"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("body", [{"count": 101}, {"count": 0}, {"feedback_policy": "never"}])
def test_quick_start_rejects_out_of_range_input(api, syllabus_tree, body):
    chapter = syllabus_tree.subjects.first().chapters.first()

    res = api.post("/mcq/quick-start/", {"chapter_id": str(chapter.id), **body})

    assert res.status_code == 400


@pytest.mark.django_db
def test_chapter_detail_reports_how_many_choice_questions_it_has(api, syllabus_tree):
    from modules.questionbank.models import Question

    course = syllabus_tree.level.course
    level = syllabus_tree.level
    subject = syllabus_tree.subjects.first()
    chapter = subject.chapters.first()
    for kind in ("mcq_single", "mcq_multi", "true_false", "long_form"):
        Question.objects.create(
            kind=kind,
            stem_head="Q",
            visibility=Question.Visibility.PUBLIC,
            status=Question.Status.ACTIVE,
            course=course,
            level=level,
            primary_chapter=chapter,
        )

    res = api.get(f"/mcq/subjects/{subject.key}/chapters/{chapter.key}/?course={course.code}&level={level.code}")

    assert res.status_code == 200
    assert res.json_body["available"] == 3
