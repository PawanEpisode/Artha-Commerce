import uuid
from unittest.mock import patch

import pytest

from core import question_port, suggestion_source_port
from modules.practice import subscribers
from modules.practice.models import QuestionState

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


@pytest.mark.django_db
def test_on_practice_session_completed_coverage_and_tracking(sample_questions):
    ch = sample_questions["chapter"]
    session_id = uuid.uuid4()

    # Mock coverage and tracking services
    with (
        patch("modules.coverage.services.record_event") as mock_record_coverage,
        patch("modules.tracking.services.add_auto_session") as mock_add_tracking,
    ):
        # 1. Payload with active_seconds < 60 (tracking shouldn't record)
        payload = {
            "session_id": str(session_id),
            "mode": "untimed",
            "active_seconds": 45,
            "by_chapter": [
                {
                    "chapter_id": str(ch.id),
                    "answered": 2,
                    "marks": 4.0,
                }
            ],
        }
        subscribers.on_practice_session_completed(payload=payload, user_id=USER)

        assert mock_record_coverage.call_count == 1
        coverage_kwargs = mock_record_coverage.call_args.kwargs
        assert coverage_kwargs["user_id"] == USER
        assert coverage_kwargs["chapter_id"] == ch.id
        assert coverage_kwargs["value"] == 4

        # Tracking should NOT be called for < 60s
        assert mock_add_tracking.call_count == 0

        # 2. Payload with active_seconds >= 60 (tracking SHOULD record)
        mock_record_coverage.reset_mock()
        mock_add_tracking.reset_mock()

        payload["active_seconds"] = 120
        subscribers.on_practice_session_completed(payload=payload, user_id=USER)

        assert mock_record_coverage.call_count == 1
        assert mock_add_tracking.call_count == 1
        tracking_kwargs = mock_add_tracking.call_args.kwargs
        assert tracking_kwargs["user_id"] == USER
        assert tracking_kwargs["chapter_id"] == ch.id
        assert tracking_kwargs["seconds"] == 120


@pytest.mark.django_db
def test_question_port_and_suggestion_source_port(sample_questions, qb_flag):
    from modules.practice import ports

    ports.register_ports()
    q1 = sample_questions["q1"]
    v1 = sample_questions["v1"]
    ch = sample_questions["chapter"]

    # 1. Question port source lookup
    provider = question_port.get_question_provider()
    assert provider is not None
    src = provider.source_for(USER, q1.id, v1.id)
    assert src is not None
    assert src.question_id == q1.id
    assert src.version_id == v1.id
    assert src.explanation_md == v1.explanation_md
    assert src.chapter_id == ch.id

    # 2. Fail closed on question port when flag is off
    qb_flag(False)
    assert provider.source_for(USER, q1.id, v1.id) is None
    qb_flag(True)

    # 3. Suggestion source for wrong_answers
    # Record a mistake state for q1
    QuestionState.objects.create(
        user_id=USER,
        question_id=q1.id,
        chapter_id=ch.id,
        last_result="incorrect",
        attempts=1,
        box=1,
    )

    source = suggestion_source_port.get_suggestion_source("wrong_answers")
    assert source is not None
    pieces = source.texts_for(USER, ch.id, limit=5)
    assert len(pieces) == 1
    assert "Section 10" in pieces[0].text

    # 4. Fail closed on suggestion source when flag is off
    qb_flag(False)
    assert source.texts_for(USER, ch.id, limit=5) == []
    qb_flag(True)
