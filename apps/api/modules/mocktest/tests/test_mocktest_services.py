"""
Integration tests for F-08 Mock Tests services.
"""

from decimal import Decimal
import uuid
import pytest
from django.utils import timezone

from modules.mocktest import services
from modules.mocktest.models import Attempt, Paper, PaperVersion
from modules.questionbank.models import Option, Question, QuestionVersion
from modules.syllabus.tests.helpers import make_scheme


USER_ID = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


@pytest.fixture
def syllabus_and_questions(db):
    scheme = make_scheme()
    level = scheme.level
    course = level.course
    subject = scheme.subjects.first()
    chapter = subject.chapters.first()

    # Question 1 (MCQ Single)
    q1 = Question.objects.create(
        course=course,
        level=level,
        primary_subject=subject,
        primary_chapter=chapter,
        kind="mcq_single",
        visibility=Question.Visibility.PUBLIC,
        status=Question.Status.ACTIVE,
    )
    v1 = QuestionVersion.objects.create(
        question=q1,
        version_no=1,
        state=QuestionVersion.State.LIVE,
        stem_md="What is Section 10?",
        stem_text="What is Section 10?",
        marks=Decimal("2.0"),
    )
    q1.live_version = v1
    q1.save(update_fields=["live_version"])
    opt1 = Option.objects.create(version=v1, body_md="Opt A", is_correct=True, position=1)
    opt2 = Option.objects.create(version=v1, body_md="Opt B", is_correct=False, position=2)

    # Question 2 (MCQ Single)
    q2 = Question.objects.create(
        course=course,
        level=level,
        primary_subject=subject,
        primary_chapter=chapter,
        kind="mcq_single",
        visibility=Question.Visibility.PUBLIC,
        status=Question.Status.ACTIVE,
    )
    v2 = QuestionVersion.objects.create(
        question=q2,
        version_no=1,
        state=QuestionVersion.State.LIVE,
        stem_md="What is Section 17(5)?",
        stem_text="What is Section 17(5)?",
        marks=Decimal("3.0"),
    )
    q2.live_version = v2
    q2.save(update_fields=["live_version"])
    opt2_1 = Option.objects.create(version=v2, body_md="Opt A", is_correct=False, position=1)
    opt2_2 = Option.objects.create(version=v2, body_md="Opt B", is_correct=True, position=2)

    return {
        "course": course,
        "level": level,
        "scheme": scheme,
        "subject": subject,
        "chapter": chapter,
        "q1": q1,
        "q2": q2,
        "opt1": opt1,
        "opt2": opt2,
        "opt2_2": opt2_2,
    }


@pytest.mark.django_db
def test_full_mock_test_lifecycle(syllabus_and_questions):
    data = syllabus_and_questions
    editor_id = uuid.uuid4()

    # 1. Create draft paper
    paper = services.create_paper_draft(
        actor_id=editor_id,
        payload={
            "course_id": data["course"].id,
            "level_id": data["level"].id,
            "scheme_id": data["scheme"].id,
            "subject_id": data["subject"].id,
            "subject_key": data["subject"].key,
            "title": "MTP Series 1 Taxation",
            "kind": Paper.Kind.MTP,
            "source_tag": Paper.SourceTag.INSTITUTE,
            "total_marks": 5.0,
            "duration_seconds": 3600,
            "reading_seconds": 900,
        },
    )
    assert paper.status == Paper.Status.DRAFT
    version = paper.versions.first()
    assert version is not None

    # 2. Set blueprint
    sections_data = [{"key": "A", "title": "Section A", "position": 1, "kind": "objective"}]
    items_data = [
        {"position": 1, "display_label": "Q.1", "question_id": data["q1"].id, "section_key": "A", "marks": 2.0},
        {"position": 2, "display_label": "Q.2", "question_id": data["q2"].id, "section_key": "A", "marks": 3.0},
    ]
    ok, problems = services.set_blueprint(editor_id, version.id, sections_data=sections_data, items_data=items_data)
    assert ok is True
    assert len(problems) == 0

    # 3. Publish paper
    pub_v = services.publish_version(editor_id, version.id, visibility=Paper.Visibility.PUBLIC)
    paper.refresh_from_db()
    assert paper.status == Paper.Status.LIVE
    assert paper.visibility == Paper.Visibility.PUBLIC
    assert pub_v.state == PaperVersion.State.LIVE

    # 4. Start attempt
    attempt = services.start_attempt(USER_ID, paper.id, run_mode="exam")
    assert attempt.phase == Attempt.Phase.INSTRUCTIONS
    assert attempt.attempt_no == 1
    assert attempt.layout[0]["pos"] == 1

    # 5. Accept instructions (has reading seconds, so moves to reading)
    attempt = services.accept_instructions(USER_ID, attempt.id)
    assert attempt.phase == Attempt.Phase.READING

    # 6. Skip reading / start writing
    attempt = services.start_writing(USER_ID, attempt.id)
    assert attempt.phase == Attempt.Phase.WRITING
    assert attempt.writing_started_at is not None

    # 7. Acquire lease
    lease = services.acquire_lease(USER_ID, attempt.id, tab_id="tab-1", label="Chrome")
    assert lease["epoch"] == 2

    # 8. Heartbeat
    hb = services.heartbeat(USER_ID, attempt.id, epoch=2, position=1)
    assert hb["phase"] == "writing"

    # 9. Save answers
    save_res = services.save_answers(
        USER_ID,
        attempt.id,
        epoch=2,
        items=[
            {"position": 1, "answer": {"selected_option_id": str(data["opt1"].id)}},
            {"position": 2, "answer": {"selected_option_id": str(data["opt2_2"].id)}},
        ],
    )
    assert len(save_res) == 2
    assert save_res[0]["status"] == "saved"

    # 10. Submit attempt
    submitted = services.submit_attempt(USER_ID, attempt.id, epoch=2)
    assert submitted.phase == Attempt.Phase.DONE
    assert submitted.score == Decimal("5.00")
    assert submitted.percent == Decimal("100.00")
    assert submitted.integrity_class == "clean"

    # 11. Delete all for user (DPDP)
    del_rep = services.delete_all_for_user(USER_ID)
    assert del_rep["attempts"] == 1
    assert Attempt.objects.filter(user_id=USER_ID).count() == 0
