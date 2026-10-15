import uuid

import pytest
from django.utils import timezone

from modules.practice import selectors, services
from modules.practice.models import QuestionState

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


@pytest.mark.django_db
def test_progress_by_chapter_and_state_stamp(sample_questions):
    ch = sample_questions["chapter"]
    other_ch_id = uuid.uuid4()

    stamp_before = selectors.state_stamp(USER)

    # Initially empty progress
    res = selectors.progress_by_chapter(USER, [ch.id, other_ch_id])
    assert ch.id in res
    assert other_ch_id in res
    assert res[ch.id].attempted == 0
    assert res[ch.id].correct_last == 0
    assert res[ch.id].wrong_last == 0
    assert res[ch.id].bookmarked == 0

    # Create session and answer
    session_res = services.create_session(
        user_id=USER,
        origin="questionbank",
        mode="untimed",
        picker="filter",
        picker_params={"chapter_ids": [str(ch.id)]},
    )
    q1 = sample_questions["q1"]
    opt1_1 = sample_questions["opt1_1"]
    services.save_answer(
        user_id=USER,
        session_id=session_res.session_id,
        question_id=q1.id,
        answer_json={"selected_option_ids": [str(opt1_1.id)]},
    )
    services.submit_session(user_id=USER, session_id=session_res.session_id)

    # Bookmark it
    services.set_question_state(user_id=USER, question_id=q1.id, bookmarked=True)

    stamp_after = selectors.state_stamp(USER)
    assert stamp_before != stamp_after

    # Now verify chapter progress
    res2 = selectors.progress_by_chapter(USER, [ch.id, other_ch_id])
    assert res2[ch.id].attempted == 1
    assert res2[ch.id].correct_last == 1
    assert res2[ch.id].wrong_last == 0
    assert res2[ch.id].bookmarked == 1
    assert res2[other_ch_id].attempted == 0


@pytest.mark.django_db
def test_list_mistakes_and_bookmarks(sample_questions):
    ch = sample_questions["chapter"]
    q1 = sample_questions["q1"]
    q2 = sample_questions["q2"]

    # Set up question states directly
    QuestionState.objects.create(
        user_id=USER,
        question_id=q1.id,
        chapter_id=ch.id,
        last_result="incorrect",
        attempts=1,
        bookmarked=True,
        bookmarked_at=timezone.now(),
        last_mistake_reason="calculation",
        note="Careful with section 10",
    )
    QuestionState.objects.create(
        user_id=USER,
        question_id=q2.id,
        chapter_id=ch.id,
        last_result="correct",
        attempts=2,
        bookmarked=False,
    )

    mistakes = selectors.list_mistakes(USER, chapter_id=ch.id)
    assert len(mistakes.items) == 1
    assert mistakes.items[0].question_id == q1.id
    assert mistakes.items[0].mistake_reason == "calculation"

    bookmarks = selectors.list_bookmarks(USER, chapter_id=ch.id)
    assert len(bookmarks.items) == 1
    assert bookmarks.items[0].question_id == q1.id
    assert bookmarks.items[0].note == "Careful with section 10"


@pytest.mark.django_db
def test_list_sessions_pagination(sample_questions):
    ch = sample_questions["chapter"]
    # Create 3 sessions
    for i in range(3):
        services.create_session(
            user_id=USER,
            origin="questionbank",
            mode="untimed",
            title=f"Session {i}",
            picker="filter",
            picker_params={"chapter_ids": [str(ch.id)]},
        )

    page1 = selectors.list_sessions(USER, limit=2)
    assert len(page1.items) == 2
    assert page1.next_cursor is not None

    page2 = selectors.list_sessions(USER, cursor=page1.next_cursor, limit=2)
    assert len(page2.items) == 1
    assert page2.next_cursor is None
