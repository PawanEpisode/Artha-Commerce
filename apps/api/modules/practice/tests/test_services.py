"""
Tests for Practice services: session lifecycle, answering, grading, retakes, and account operations.
"""

from decimal import Decimal

import pytest

from modules.practice import services
from modules.practice.models import (
    AttemptAnswer,
    DailyRollup,
    QuestionState,
    Session,
)
from modules.practice.tests.conftest import USER

pytestmark = pytest.mark.django_db


def test_create_session(sample_questions):
    ch = sample_questions["chapter"]
    session_res = services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="untimed",
        title="Test Session",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)], "count": 10},
    )
    assert session_res.question_count == 3
    assert session_res.status == Session.Status.CREATED

    session = Session.objects.get(id=session_res.session_id)
    assert session.total_marks == Decimal("8.0")
    answers = AttemptAnswer.objects.filter(session_id=session.id).order_by("position")
    assert answers.count() == 3
    # Check that each answer is linked to chapter_id (E-F06-1)
    for ans in answers:
        assert ans.chapter_id == ch.id


def test_create_session_from_items(sample_questions):
    q1 = sample_questions["q1"]
    v1 = sample_questions["v1"]
    session = services.create_session_from_items(
        user_id=USER,
        origin="questionbank",
        mode="exam",
        title="Exam Session",
        items=[
            {
                "question_id": str(q1.id),
                "version_id": str(v1.id),
                "marks": 2.0,
                "negative_marks": 0.5,
                "section_label": "Section A",
            }
        ],
        time_limit_seconds=3600,
    )
    assert session.question_count == 1
    assert session.mode == Session.Mode.EXAM
    assert session.time_limit_seconds == 3600
    assert session.feedback_policy == Session.FeedbackPolicy.NEVER_UNTIL_SUBMIT


def test_save_answer_and_last_write_wins(sample_questions):
    ch = sample_questions["chapter"]
    session_res = services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="untimed",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)]},
    )
    q1 = sample_questions["q1"]
    opt1_1 = sample_questions["opt1_1"]

    # 1. First save
    ans_saved = services.save_answer(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q1.id,
        answer_json={"selected_option_ids": [str(opt1_1.id)]},
        client_ts="2026-10-15T10:00:00Z",
        time_spent_ms=15000,
    )
    assert ans_saved.status == AttemptAnswer.Status.ANSWERED

    ans = AttemptAnswer.objects.get(session_id=session_res.session_id, question_id=q1.id)
    assert ans.selected_option_ids == [str(opt1_1.id)]
    assert ans.time_spent_ms == 15000
    assert ans.first_seen_at is not None

    # 2. Older client_ts is ignored (LWW)
    services.save_answer(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q1.id,
        answer_json={"selected_option_ids": ["stale"]},
        client_ts="2026-10-15T09:00:00Z",
    )
    ans.refresh_from_db()
    assert ans.selected_option_ids == [str(opt1_1.id)]


def test_check_answer_instant(sample_questions):
    ch = sample_questions["chapter"]
    session_res = services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="untimed",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)]},
        config={"feedback_policy": "instant"},
    )
    q1 = sample_questions["q1"]
    opt1_1 = sample_questions["opt1_1"]

    fb = services.check_answer(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q1.id,
        answer_json={"selected_option_ids": [str(opt1_1.id)]},
    )
    assert fb.result == "correct"
    assert fb.marks_awarded == Decimal("2.0")
    assert fb.explanation_md != ""

    ans = AttemptAnswer.objects.get(session_id=session_res.session_id, question_id=q1.id)
    assert ans.status == AttemptAnswer.Status.GRADED

    # Modifying a graded answer raises AnswerLocked
    with pytest.raises(services.AnswerLocked):
        services.save_answer(
            user_id=USER,
            session_id=session_res.session_id,
            question_id=q1.id,
            answer_json={"selected_option_ids": []},
        )


def test_pause_and_resume_session(sample_questions):
    ch = sample_questions["chapter"]
    session_res = services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="timed",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)]},
        config={"time_limit_seconds": 1800, "allow_pause": True},
    )
    session = Session.objects.get(id=session_res.session_id)
    # Start it
    services.save_answer(
        user_id=USER,
        session_id=session.id,
        position=1,
        answer_json={},
    )
    session.refresh_from_db()
    assert session.status == Session.Status.IN_PROGRESS

    # Pause
    services.pause_session(user_id=USER, session_id=session.id)
    session.refresh_from_db()
    assert session.status == Session.Status.PAUSED
    assert session.paused_at is not None

    # Resume
    services.resume_session(user_id=USER, session_id=session.id)
    session.refresh_from_db()
    assert session.status == Session.Status.IN_PROGRESS
    assert session.paused_at is None


def test_submit_session_and_leitner_box_progression(sample_questions, events):
    ch = sample_questions["chapter"]
    session_res = services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="untimed",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)]},
    )
    q1 = sample_questions["q1"]
    opt1_1 = sample_questions["opt1_1"]  # correct
    q2 = sample_questions["q2"]
    opt2_3 = sample_questions["opt2_3"]  # incorrect

    # Answer Q1 correctly
    services.save_answer(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q1.id,
        answer_json={"selected_option_ids": [str(opt1_1.id)]},
    )
    # Answer Q2 incorrectly
    services.save_answer(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q2.id,
        answer_json={"selected_option_ids": [str(opt2_3.id)]},
    )

    # Submit
    result = services.submit_session(user_id=USER, session_id=session_res.session_id)
    assert result.score == Decimal("1.50")  # 2.0 (correct) - 0.5 (incorrect penalty)
    assert result.counts["answered"] == 2
    assert result.counts["skipped"] == 1

    session = Session.objects.get(id=session_res.session_id)
    assert session.status == Session.Status.SUBMITTED

    # Check Leitner progression on QuestionState (E-F06-1)
    qs1 = QuestionState.objects.get(user_id=USER, question_id=q1.id)
    assert qs1.box == 1
    assert qs1.correct_streak == 1
    assert qs1.chapter_id == ch.id

    qs2 = QuestionState.objects.get(user_id=USER, question_id=q2.id)
    assert qs2.box == 0
    assert qs2.correct_streak == 0
    assert qs2.chapter_id == ch.id

    # Check DailyRollup
    rollups = DailyRollup.objects.filter(user_id=USER, chapter_id=ch.id)
    assert rollups.exists()
    r = rollups.first()
    assert r.answered == 2
    assert r.correct == 1
    assert r.incorrect == 1

    # Check practice_session_completed event was emitted
    emitted_names = [e["name"] for e in events]
    assert "practice_session_completed" in emitted_names


def test_retake_session(sample_questions):
    ch = sample_questions["chapter"]
    session_res = services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="untimed",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)]},
    )
    q1 = sample_questions["q1"]
    opt1_2 = sample_questions["opt1_2"]  # incorrect

    # Answer Q1 wrong
    services.save_answer(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q1.id,
        answer_json={"selected_option_ids": [str(opt1_2.id)]},
    )
    services.submit_session(user_id=USER, session_id=session_res.session_id)

    # Retake wrong only
    retake_res = services.retake(
        user_id=USER,
        session_id=session_res.session_id,
        scope="wrong",
    )
    assert retake_res.question_count == 1
    new_session = Session.objects.get(id=retake_res.session_id)
    assert new_session.retake_of_id == session_res.session_id


def test_set_mistake_reason_and_question_state(sample_questions):
    ch = sample_questions["chapter"]
    session_res = services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="untimed",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)]},
    )
    q1 = sample_questions["q1"]

    services.save_answer(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q1.id,
        answer_json={},
    )

    services.set_mistake_reason(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q1.id,
        mistake_reason="calculation",
    )
    ans = AttemptAnswer.objects.get(session_id=session_res.session_id, question_id=q1.id)
    assert ans.mistake_reason == "calculation"

    state = services.set_question_state(
        user_id=USER,
        question_id=q1.id,
        bookmarked=True,
        notes="Revise Section 10 provisions",
    )
    assert state.bookmarked is True
    assert state.notes == "Revise Section 10 provisions"


def test_erasure_and_export(sample_questions):
    ch = sample_questions["chapter"]
    services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="untimed",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)]},
    )
    exported = services.export_for_user(USER)
    assert "sessions" in exported
    assert len(exported["sessions"]) >= 1

    services.delete_all_for_user(USER)
    assert Session.objects.filter(user_id=USER).count() == 0
    assert AttemptAnswer.objects.filter(user_id=USER).count() == 0
    assert QuestionState.objects.filter(user_id=USER).count() == 0
