import uuid

import pytest

from modules.practice import selectors
from modules.practice.models import Session

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


@pytest.mark.django_db
def test_answer_isolation_during_active_session(sample_questions, api):
    ch = sample_questions["chapter"]

    # Create active session
    create_res = api.post(
        "/api/v1/practice/sessions/",
        {
            "origin": "questionbank",
            "mode": "untimed",
            "picker": "filter",
            "picker_params": {"chapter_ids": [str(ch.id)]},
        },
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]

    # 1. Check via selector directly
    session_view = selectors.get_session(USER, uuid.UUID(session_id))
    assert session_view.status == Session.Status.CREATED
    assert session_view.score is None
    for it in session_view.items:
        assert it.explanation_md is None
        assert it.result is None
        assert it.marks_awarded is None
        for opt in it.options:
            assert "is_correct" not in opt
            assert "feedback_md" not in opt

    # 2. Check via API endpoint GET /api/v1/practice/sessions/<id>/
    resp = api.get(f"/api/v1/practice/sessions/{session_id}/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == Session.Status.CREATED
    assert data["score"] is None

    # Strict string inspection of raw JSON to ensure no secret fields leak
    raw_text = resp.content.decode()
    assert "is_correct" not in raw_text
    assert "feedback_md" not in raw_text
    assert "tolerance_abs" not in raw_text
    # Ensure secret explanation content is strictly absent
    assert "Option A is correct according to Section 10." not in raw_text
    for it in data["items"]:
        assert it["explanation_md"] is None

    # 3. Submit session
    sub_res = api.post(f"/api/v1/practice/sessions/{session_id}/submit/")
    assert sub_res.status_code == 200

    # 4. Review via GET endpoint should now expose explanations and correctness
    rev_resp = api.get(f"/api/v1/practice/sessions/{session_id}/")
    assert rev_resp.status_code == 200
    rev_data = rev_resp.json()
    assert rev_data["status"] == Session.Status.SUBMITTED
    assert rev_data["score"] is not None

    rev_raw_text = rev_resp.content.decode()
    assert "is_correct" in rev_raw_text
    assert "explanation_md" in rev_raw_text
