import uuid

import pytest

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")


@pytest.mark.django_db
def test_full_session_api_lifecycle(sample_questions, api):
    ch = sample_questions["chapter"]
    q1 = sample_questions["q1"]
    opt1_1 = sample_questions["opt1_1"]

    # 1. Create session
    create_res = api.post(
        "/practice/sessions/",
        {
            "origin": "questionbank",
            "mode": "untimed",
            "feedback_policy": "instant",
            "picker": "filter",
            "picker_params": {"chapter_ids": [str(ch.id)]},
            "config": {"allow_pause": True},
        },
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]

    # 2. Get session
    detail_res = api.get(f"/practice/sessions/{session_id}/")
    assert detail_res.status_code == 200
    assert detail_res.json()["id"] == session_id

    # 3. Save answer
    save_res = api.post(
        f"/practice/sessions/{session_id}/answers/{q1.id}/",
        {
            "answer_json": {"selected_option_ids": [str(opt1_1.id)]},
            "time_spent_ms": 15000,
            "confidence": 1,
        },
    )
    assert save_res.status_code == 200
    assert save_res.json()["status"] == "saved"

    # 4. Instant check
    check_res = api.post(
        f"/practice/sessions/{session_id}/answers/{q1.id}/check/",
        {
            "answer_json": {"selected_option_ids": [str(opt1_1.id)]},
        },
    )
    assert check_res.status_code == 200
    assert check_res.json()["result"] == "correct"

    # 5. Pause and Resume
    pause_res = api.post(f"/practice/sessions/{session_id}/pause/")
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "paused"

    resume_res = api.post(f"/practice/sessions/{session_id}/resume/")
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "in_progress"

    # 6. Submit
    submit_res = api.post(f"/practice/sessions/{session_id}/submit/")
    assert submit_res.status_code == 200
    assert submit_res.json()["status"] == "submitted"

    # 7. Mistake reason
    reason_res = api.post(
        f"/practice/sessions/{session_id}/answers/{q1.id}/mistake-reason/",
        {"mistake_reason": "silly"},
    )
    assert reason_res.status_code == 200
    assert reason_res.json()["mistake_reason"] == "silly"

    # 8. Retake
    retake_res = api.post(
        f"/practice/sessions/{session_id}/retake/",
        {"scope": "all"},
    )
    assert retake_res.status_code == 201
    assert retake_res.json()["id"] != session_id


@pytest.mark.django_db
def test_question_state_and_chapter_progress_endpoints(sample_questions, api):
    ch = sample_questions["chapter"]
    q1 = sample_questions["q1"]

    # 1. Update question state
    state_res = api.post(
        f"/practice/questions/{q1.id}/state/",
        {"bookmarked": True, "notes": "Important concept for exams"},
    )
    assert state_res.status_code == 200
    assert state_res.json()["status"] == "updated"

    # 2. Bookmarks list
    bkm_res = api.get("/practice/bookmarks/")
    assert bkm_res.status_code == 200
    items = bkm_res.json()["items"]
    assert len(items) >= 1
    assert any(it["question_id"] == str(q1.id) for it in items)

    # 3. Chapter progress with conditional 304 ETag
    prog_res1 = api.get(f"/practice/progress/chapters/?chapter_ids={ch.id}")
    assert prog_res1.status_code == 200
    etag = prog_res1.headers.get("ETag")
    assert etag is not None

    # Request again with If-None-Match
    prog_res2 = api.get(
        f"/practice/progress/chapters/?chapter_ids={ch.id}",
        HTTP_IF_NONE_MATCH=etag,
    )
    assert prog_res2.status_code == 304


@pytest.mark.django_db
def test_feature_flag_fails_closed(sample_questions, api, qb_flag):
    # Disable flag
    qb_flag(False)

    # All practice endpoints must fail closed (404)
    res = api.get("/practice/sessions/")
    assert res.status_code == 404

    res2 = api.get("/practice/bookmarks/")
    assert res2.status_code == 404

    res3 = api.post("/practice/sessions/", {"origin": "questionbank", "mode": "untimed"})
    assert res3.status_code == 404
