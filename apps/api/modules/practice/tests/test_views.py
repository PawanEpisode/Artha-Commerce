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


def _create_timed_session(api, chapter, *, limit: int | None = 600) -> str:
    body = {
        "origin": "questionbank",
        "mode": "timed" if limit else "untimed",
        "picker": "filter",
        "picker_params": {"chapter_ids": [str(chapter.id)]},
    }
    if limit:
        body["config"] = {"time_limit_seconds": limit}
    res = api.post("/practice/sessions/", body)
    assert res.status_code == 201
    return res.json()["id"]


@pytest.mark.django_db
def test_start_session_starts_the_clock_once(sample_questions, api):
    from datetime import datetime

    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)

    before = api.get(f"/practice/sessions/{session_id}/").json()
    assert before["status"] == "created"
    assert before["started_at"] is None
    assert before["deadline_at"] is None
    assert before["server_now"]

    first = api.post(f"/practice/sessions/{session_id}/start/")
    assert first.status_code == 200
    assert first.json()["status"] == "in_progress"
    started = datetime.fromisoformat(first.json()["started_at"])
    deadline = datetime.fromisoformat(first.json()["deadline_at"])
    assert (deadline - started).total_seconds() == 600

    again = api.post(f"/practice/sessions/{session_id}/start/")
    assert again.status_code == 200
    assert again.json()["started_at"] == first.json()["started_at"]
    assert again.json()["deadline_at"] == first.json()["deadline_at"]


@pytest.mark.django_db
def test_untimed_session_start_has_no_deadline(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=None)

    res = api.post(f"/practice/sessions/{session_id}/start/")

    assert res.status_code == 200
    assert res.json()["started_at"] is not None
    assert res.json()["deadline_at"] is None
    assert res.json()["time_limit_seconds"] is None


@pytest.mark.django_db
def test_start_unknown_session_is_404(api):
    res = api.post(f"/practice/sessions/{uuid.uuid4()}/start/")

    assert res.status_code == 404


@pytest.mark.django_db
def test_active_session_follows_the_session_through_its_life(sample_questions, api):
    chapter = sample_questions["chapter"]
    assert api.get("/practice/sessions/active/").json() == {"session": None}

    session_id = _create_timed_session(api, chapter, limit=600)
    # Created but not opened: no clock is running yet.
    assert api.get("/practice/sessions/active/").json() == {"session": None}

    api.post(f"/practice/sessions/{session_id}/start/")
    active = api.get("/practice/sessions/active/").json()["session"]
    assert active["id"] == session_id
    assert active["status"] == "in_progress"
    assert active["time_limit_seconds"] == 600
    assert active["deadline_at"]

    api.post(f"/practice/sessions/{session_id}/pause/")
    paused = api.get("/practice/sessions/active/").json()["session"]
    assert paused["status"] == "paused"
    assert paused["paused_at"]

    api.post(f"/practice/sessions/{session_id}/resume/")
    api.post(f"/practice/sessions/{session_id}/submit/")
    assert api.get("/practice/sessions/active/").json() == {"session": None}


@pytest.mark.django_db
def test_active_session_ignores_sessions_left_alone_for_a_long_time(sample_questions, api):
    from datetime import timedelta

    from django.utils import timezone

    from modules.practice.models import Session

    session_id = _create_timed_session(api, sample_questions["chapter"], limit=None)
    api.post(f"/practice/sessions/{session_id}/start/")
    Session.objects.filter(id=session_id).update(last_active_at=timezone.now() - timedelta(hours=13))

    assert api.get("/practice/sessions/active/").json() == {"session": None}


@pytest.mark.django_db
def test_pause_before_any_answer_starts_and_pauses_instead_of_409(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)

    first = api.post(f"/practice/sessions/{session_id}/pause/")
    again = api.post(f"/practice/sessions/{session_id}/pause/")

    assert first.status_code == 200
    assert again.status_code == 200  # a double tap is not an error
    paused = api.get("/practice/sessions/active/").json()["session"]
    assert paused["status"] == "paused"
    assert paused["started_at"]
    assert api.post(f"/practice/sessions/{session_id}/resume/").status_code == 200


@pytest.mark.django_db
def test_pause_after_submit_is_still_409(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)
    assert api.post(f"/practice/sessions/{session_id}/submit/").status_code == 200

    res = api.post(f"/practice/sessions/{session_id}/pause/")

    assert res.status_code == 409


def _overdue(session_id: str, seconds_ago: int) -> None:
    from datetime import timedelta

    from django.utils import timezone

    from modules.practice.models import Session

    Session.objects.filter(id=session_id).update(deadline_at=timezone.now() - timedelta(seconds=seconds_ago))


def _status(session_id: str) -> str:
    from modules.practice.models import Session

    return Session.objects.get(id=session_id).status


@pytest.mark.django_db
def test_reading_an_expired_session_auto_submits_it(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)
    api.post(f"/practice/sessions/{session_id}/start/")
    _overdue(session_id, 60)

    res = api.get(f"/practice/sessions/{session_id}/")

    assert res.status_code == 200
    assert res.json()["status"] == "auto_submitted"
    assert _status(session_id) == "auto_submitted"


@pytest.mark.django_db
def test_session_just_past_its_deadline_is_still_open_within_the_grace(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)
    api.post(f"/practice/sessions/{session_id}/start/")
    _overdue(session_id, 2)  # the student's own last save or submit may still be on its way

    res = api.get(f"/practice/sessions/{session_id}/")

    assert res.json()["status"] == "in_progress"


@pytest.mark.django_db
def test_saving_an_answer_after_time_is_up_is_409_and_closes_the_session(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)
    api.post(f"/practice/sessions/{session_id}/start/")
    _overdue(session_id, 60)
    q1, opt = sample_questions["q1"], sample_questions["opt1_1"]

    res = api.post(
        f"/practice/sessions/{session_id}/answers/{q1.id}/",
        {"answer_json": {"selected_option_ids": [str(opt.id)]}},
    )

    assert res.status_code == 409
    assert _status(session_id) == "auto_submitted"


@pytest.mark.django_db
def test_pausing_after_time_is_up_is_409_and_closes_the_session(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)
    api.post(f"/practice/sessions/{session_id}/start/")
    _overdue(session_id, 60)

    res = api.post(f"/practice/sessions/{session_id}/pause/")

    assert res.status_code == 409
    assert _status(session_id) == "auto_submitted"


@pytest.mark.django_db
def test_active_session_endpoint_closes_an_expired_session_and_reports_none(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)
    api.post(f"/practice/sessions/{session_id}/start/")
    _overdue(session_id, 60)

    res = api.get("/practice/sessions/active/")

    assert res.json() == {"session": None}
    assert _status(session_id) == "auto_submitted"


@pytest.mark.django_db
def test_listing_sessions_closes_expired_ones(sample_questions, api):
    session_id = _create_timed_session(api, sample_questions["chapter"], limit=600)
    api.post(f"/practice/sessions/{session_id}/start/")
    _overdue(session_id, 60)

    api.get("/practice/sessions/")

    assert _status(session_id) == "auto_submitted"


@pytest.mark.django_db
def test_paused_and_untimed_sessions_never_expire(sample_questions, api):
    chapter = sample_questions["chapter"]
    paused = _create_timed_session(api, chapter, limit=600)
    api.post(f"/practice/sessions/{paused}/start/")
    api.post(f"/practice/sessions/{paused}/pause/")
    _overdue(paused, 3600)
    untimed = _create_timed_session(api, chapter, limit=None)
    api.post(f"/practice/sessions/{untimed}/start/")

    api.get("/practice/sessions/")

    assert _status(paused) == "paused"
    assert _status(untimed) == "in_progress"


@pytest.mark.django_db
def test_sweep_command_closes_expired_sessions_nobody_reopened(sample_questions, api):
    from io import StringIO

    from django.core.management import call_command

    chapter = sample_questions["chapter"]
    expired = _create_timed_session(api, chapter, limit=600)
    api.post(f"/practice/sessions/{expired}/start/")
    _overdue(expired, 60)
    running = _create_timed_session(api, chapter, limit=600)
    api.post(f"/practice/sessions/{running}/start/")

    out = StringIO()
    call_command("expire_practice_sessions", stdout=out)

    assert "1 expired" in out.getvalue()
    assert _status(expired) == "auto_submitted"
    assert _status(running) == "in_progress"
    out2 = StringIO()
    call_command("expire_practice_sessions", stdout=out2)  # a second run has nothing left to do
    assert "0 expired" in out2.getvalue()


@pytest.mark.django_db
def test_allow_pause_is_reported_and_enforced(sample_questions, api):
    chapter = sample_questions["chapter"]
    locked = api.post(
        "/practice/sessions/",
        {
            "origin": "questionbank",
            "mode": "untimed",
            "picker": "filter",
            "picker_params": {"chapter_ids": [str(chapter.id)]},
            "config": {"allow_pause": False},
        },
    ).json()["id"]
    normal = _create_timed_session(api, chapter, limit=None)

    assert api.get(f"/practice/sessions/{locked}/").json()["allow_pause"] is False
    assert api.get(f"/practice/sessions/{normal}/").json()["allow_pause"] is True
    assert api.post(f"/practice/sessions/{locked}/pause/").status_code == 403
    assert api.post(f"/practice/sessions/{normal}/pause/").status_code == 200
