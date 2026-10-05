import uuid
from datetime import timedelta

import pytest

from modules.coverage.models import ChapterProgress, CoverageEvent
from modules.tracking import services
from modules.tracking.models import DailyRollup, HourBucket, SessionAudit, StudySession

from .conftest import NOW, USER, iso, ist, manual

pytestmark = pytest.mark.django_db


def test_manual_entry_needs_a_signed_in_student(client):
    assert client.post("/api/v1/tracking/sessions/", {}, content_type="application/json").status_code in (401, 403)
    assert client.get("/api/v1/tracking/sessions/").status_code in (401, 403)


def test_manual_entry_by_start_and_end_stores_a_source_manual_session(api):
    res = manual(api, ist(4, 19), ist(4, 21), activity_type="revision", note="Company law")
    assert res.status_code == 201, res.json_body
    body = res.json_body
    assert (body["source"], body["focus_seconds"], body["study_date"]) == ("manual", 7200, "2026-10-04")
    assert (body["activity_type"], body["note"], body["tz"]) == ("revision", "Company law", "Asia/Kolkata")


def test_manual_entry_by_start_and_duration(api):
    res = manual(api, ist(4, 9), minutes=45)
    assert res.status_code == 201 and res.json_body["focus_seconds"] == 2700


def test_manual_entry_with_no_end_or_duration_is_rejected(api):
    res = manual(api, ist(4, 9))
    assert res.status_code == 400


def test_the_same_client_id_never_creates_a_second_session(api):
    body = {"client_id": str(uuid.uuid4()), "started_at": iso(ist(4, 9)), "ended_at": iso(ist(4, 10))}
    first, second = api.post("/tracking/sessions/", body), api.post("/tracking/sessions/", body)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json_body["id"] == second.json_body["id"]
    assert StudySession.objects.count() == 1


@pytest.mark.parametrize(
    ("start", "end", "code"),
    [
        (ist(6, 9), ist(6, 10), "future"),
        (ist(5, 9), ist(5, 9, 0), "end_before_start"),
        (ist(4, 9), ist(4, 9, 0), "end_before_start"),
        (ist(3, 9), ist(3, 9) + timedelta(seconds=40), "too_short"),
        (ist(1, 0), ist(3, 1), "too_long"),
    ],
)
def test_manual_entry_limits(api, start, end, code):
    res = manual(api, start, end)
    assert res.status_code == 400 and res.json_body["error"]["code"] == code, res.json_body
    assert StudySession.objects.count() == 0


def test_old_entries_need_a_confirmation_and_very_old_ones_are_refused(api):
    old = NOW - timedelta(days=90)
    res = manual(api, old, old + timedelta(hours=1))
    assert res.status_code == 400 and res.json_body["error"]["code"] == "confirmation_required"
    ok = manual(api, old, old + timedelta(hours=1), confirm_old=True)
    assert ok.status_code == 201
    too_old = NOW - timedelta(days=400)
    assert manual(api, too_old, too_old + timedelta(hours=1), confirm_old=True).json_body["error"]["code"] == "too_old"


def test_tags_are_validated_and_a_chapter_fills_in_its_subject(api, ids):
    res = manual(api, ist(4, 9), minutes=30, chapter_id=ids["gst"])
    assert res.status_code == 201
    assert (res.json_body["subject_id"], res.json_body["chapter_id"]) == (ids["taxation"], ids["gst"])
    assert res.json_body["chapter_name"] == "GST: Input Tax Credit"
    wrong = manual(api, ist(3, 9), minutes=30, subject_id=ids["laws"], chapter_id=ids["gst"])
    assert wrong.status_code == 400
    assert manual(api, ist(2, 9), minutes=30, subject_id=str(uuid.uuid4())).status_code == 400
    assert manual(api, ist(1, 9), minutes=30, activity_type="gaming").status_code == 400


def test_a_long_note_is_refused(api):
    assert manual(api, ist(4, 9), minutes=30, note="x" * 501).status_code == 400


def test_overlap_answers_409_with_the_conflicting_ids_and_offers_three_choices(api):
    first = manual(api, ist(4, 9), ist(4, 11)).json_body
    res = manual(api, ist(4, 10), ist(4, 12))
    assert res.status_code == 409 and res.json_body["error"]["code"] == "overlap"
    assert res.json_body["error"]["details"]["conflicts"] == [first["id"]]
    kept = manual(api, ist(4, 10), ist(4, 12), on_overlap="keep")
    assert kept.status_code == 201 and kept.json_body["overlaps_other"] is True
    trimmed = manual(api, ist(4, 8), ist(4, 12, 30), on_overlap="trim")  # free: 08:00-09:00 and 12:00-12:30
    assert trimmed.status_code == 201
    assert (trimmed.json_body["started_at"], trimmed.json_body["focus_seconds"]) == (iso(ist(4, 8)), 3600)
    assert SessionAudit.objects.filter(action="manual_trim").count() == 1


def test_trim_with_nothing_left_is_refused(api):
    manual(api, ist(4, 9), ist(4, 12))
    res = manual(api, ist(4, 10), ist(4, 11), on_overlap="trim")
    assert res.status_code == 400 and res.json_body["error"]["code"] == "fully_overlapped"


def test_a_session_across_midnight_lands_in_both_days_and_hours(api):
    res = manual(api, ist(4, 23, 30), ist(5, 1, 30))
    assert res.status_code == 201 and res.json_body["study_date"] == "2026-10-04"
    days = {str(r.study_date): (r.seconds, r.sessions) for r in DailyRollup.objects.filter(user_id=USER)}
    assert days == {"2026-10-04": (1800, 1), "2026-10-05": (5400, 0)}  # the session counts once, on its start day
    hours = {(str(h.study_date), h.hour): h.seconds for h in HourBucket.objects.filter(user_id=USER)}
    assert hours == {("2026-10-04", 23): 1800, ("2026-10-05", 0): 3600, ("2026-10-05", 1): 1800}


def test_list_filters_and_pages_newest_first(api, ids):
    for i in range(5):
        manual(api, ist(1 + i, 9), minutes=30 + i, subject_id=ids["taxation"] if i % 2 == 0 else ids["laws"])
    all_rows = api.get("/tracking/sessions/?limit=2").json_body
    assert len(all_rows["results"]) == 2 and all_rows["next_cursor"]
    assert all_rows["results"][0]["study_date"] == "2026-10-05"
    page2 = api.get(f"/tracking/sessions/?limit=2&cursor={all_rows['next_cursor']}").json_body
    assert [r["study_date"] for r in page2["results"]] == ["2026-10-03", "2026-10-02"]
    tax = api.get(f"/tracking/sessions/?subject_id={ids['taxation']}").json_body["results"]
    assert len(tax) == 3
    day = api.get("/tracking/sessions/?from=2026-10-02&to=2026-10-03").json_body["results"]
    assert len(day) == 2
    assert api.get("/tracking/sessions/?source=pomodoro").json_body["results"] == []
    assert api.get("/tracking/sessions/?cursor=garbage").status_code == 400


def test_edit_tags_and_note_do_not_count_as_a_time_edit(api, ids):
    sid = manual(api, ist(4, 9), minutes=60).json_body["id"]
    res = api.patch(
        f"/tracking/sessions/{sid}/", {"subject_id": ids["taxation"], "note": "ok", "activity_type": "practice"}
    )
    assert res.status_code == 200
    assert (res.json_body["is_edited"], res.json_body["subject_name"], res.json_body["activity_type"]) == (
        False,
        "Taxation",
        "practice",
    )
    assert DailyRollup.objects.get(user_id=USER).subject_id is not None


def test_changing_the_subject_drops_a_chapter_that_no_longer_fits(api, ids):
    sid = manual(api, ist(4, 9), minutes=60, chapter_id=ids["gst"]).json_body["id"]
    res = api.patch(f"/tracking/sessions/{sid}/", {"subject_id": ids["laws"]})
    assert res.status_code == 200 and res.json_body["chapter_id"] is None and res.json_body["subject_id"] == ids["laws"]


def test_editing_times_updates_totals_and_keeps_the_original(api):
    sid = manual(api, ist(4, 9), ist(4, 10)).json_body["id"]
    res = api.patch(f"/tracking/sessions/{sid}/", {"ended_at": iso(ist(4, 9, 45))})
    assert res.status_code == 200 and res.json_body["focus_seconds"] == 2700 and res.json_body["is_edited"] is True
    row = StudySession.objects.get(pk=sid)
    assert row.original_ended_at == ist(4, 10) and row.edit_count == 1
    assert DailyRollup.objects.get(user_id=USER).seconds == 2700
    assert SessionAudit.objects.filter(action="edit_times").count() == 1


def test_an_edit_that_moves_the_day_updates_both_days(api):
    sid = manual(api, ist(4, 9), ist(4, 10)).json_body["id"]
    api.patch(f"/tracking/sessions/{sid}/", {"started_at": iso(ist(3, 9)), "ended_at": iso(ist(3, 10))})
    assert {str(r.study_date): r.seconds for r in DailyRollup.objects.all()} == {"2026-10-03": 3600}


def test_pomodoro_rounds_keep_their_times_but_can_be_retagged(api, ids):
    s, _ = services.record_session(
        USER,
        source="pomodoro",
        started_at=ist(4, 9),
        ended_at=ist(4, 9, 25),
        focus_seconds=1500,
        round_number=1,
        cycle_id=uuid.uuid4(),
    )
    bad = api.patch(f"/tracking/sessions/{s.id}/", {"ended_at": iso(ist(4, 10))})
    assert bad.status_code == 400 and bad.json_body["error"]["code"] == "pomodoro_times_fixed"
    assert api.patch(f"/tracking/sessions/{s.id}/", {"subject_id": ids["laws"]}).status_code == 200


def test_edit_validates_times(api):
    sid = manual(api, ist(4, 9), ist(4, 10)).json_body["id"]
    assert api.patch(f"/tracking/sessions/{sid}/", {"ended_at": iso(ist(4, 8))}).status_code == 400
    assert api.patch(f"/tracking/sessions/{sid}/", {"ended_at": iso(ist(9, 8))}).status_code == 400  # future


def test_delete_then_undo_within_ten_seconds_restores_the_same_id(api, clock):
    sid = manual(api, ist(4, 9), ist(4, 10), note="private").json_body["id"]
    res = api.delete(f"/tracking/sessions/{sid}/")
    assert res.status_code == 200
    assert not StudySession.objects.exists() and not DailyRollup.objects.exists()
    assert "private" not in str(SessionAudit.objects.get().snapshot)  # notes never enter the trail
    clock.advance(seconds=8)
    back = api.post("/tracking/sessions/undo/", {"undo_token": res.json_body["undo_token"], "notes": {sid: "private"}})
    assert back.status_code == 200 and back.json_body["sessions"][0]["id"] == sid
    assert back.json_body["sessions"][0]["note"] == "private"
    assert DailyRollup.objects.get().seconds == 3600
    assert (
        api.post("/tracking/sessions/undo/", {"undo_token": res.json_body["undo_token"]}).status_code == 404
    )  # used up


def test_undo_after_ten_seconds_answers_410(api, clock):
    sid = manual(api, ist(4, 9), ist(4, 10)).json_body["id"]
    token = api.delete(f"/tracking/sessions/{sid}/").json_body["undo_token"]
    clock.advance(seconds=11)
    res = api.post("/tracking/sessions/undo/", {"undo_token": token})
    assert res.status_code == 410 and not StudySession.objects.exists()


def test_merge_adjacent_sessions(api, ids):
    a = manual(api, ist(4, 9), ist(4, 10), subject_id=ids["taxation"]).json_body["id"]
    b = manual(api, ist(4, 10, 20), ist(4, 11), subject_id=ids["taxation"]).json_body["id"]
    res = api.post("/tracking/sessions/merge/", {"session_ids": [a, b]})
    assert res.status_code == 201, res.json_body
    merged = res.json_body["session"]
    assert (merged["focus_seconds"], merged["merged_count"], merged["subject_name"]) == (6000, 2, "Taxation")
    assert merged["paused_total_seconds"] == 1200
    assert StudySession.objects.count() == 1 and DailyRollup.objects.get().seconds == 6000


def test_merge_rules(api, ids):
    a = manual(api, ist(4, 9), ist(4, 10), subject_id=ids["taxation"]).json_body["id"]
    b = manual(api, ist(4, 10, 10), ist(4, 11), subject_id=ids["laws"]).json_body["id"]
    far = manual(api, ist(4, 16), ist(4, 17)).json_body["id"]
    other_day = manual(api, ist(3, 10, 5), ist(3, 11)).json_body["id"]
    assert (
        api.post("/tracking/sessions/merge/", {"session_ids": [a, b]}).json_body["error"]["code"] == "choice_required"
    )
    ok = api.post("/tracking/sessions/merge/", {"session_ids": [a, b], "subject_id": ids["laws"]})
    assert ok.status_code == 201 and ok.json_body["session"]["subject_name"] == "Corporate and Other Laws"
    assert (
        api.post("/tracking/sessions/merge/", {"session_ids": [ok.json_body["session"]["id"], far]}).json_body["error"][
            "code"
        ]
        == "too_far_apart"
    )
    assert (
        api.post("/tracking/sessions/merge/", {"session_ids": [far, other_day]}).json_body["error"]["code"]
        == "different_days"
    )
    assert api.post("/tracking/sessions/merge/", {"session_ids": [far]}).status_code == 400


def test_undo_a_merge_brings_back_the_originals(api):
    a = manual(api, ist(4, 9), ist(4, 10)).json_body["id"]
    b = manual(api, ist(4, 10, 10), ist(4, 11)).json_body["id"]
    res = api.post("/tracking/sessions/merge/", {"session_ids": [a, b]}).json_body
    assert api.post("/tracking/sessions/undo/", {"undo_token": res["undo_token"]}).status_code == 200
    assert sorted(str(i) for i in StudySession.objects.values_list("id", flat=True)) == sorted([a, b])
    assert DailyRollup.objects.get().seconds == 6600


def test_split_a_session_and_undo_it(api):
    sid = manual(api, ist(4, 9), ist(4, 10, 30), subject_id=None).json_body["id"]
    res = api.post(f"/tracking/sessions/{sid}/split/", {"at": iso(ist(4, 9, 40))})
    assert res.status_code == 201, res.json_body
    first, second = res.json_body["sessions"]
    assert (first["id"], first["focus_seconds"], second["focus_seconds"]) == (sid, 2400, 3000)
    assert second["split_from_id"] == sid
    assert DailyRollup.objects.get().seconds == 5400
    assert api.post("/tracking/sessions/undo/", {"undo_token": res.json_body["undo_token"]}).status_code == 200
    assert StudySession.objects.get().focus_seconds == 5400


def test_split_rules(api):
    sid = manual(api, ist(4, 9), ist(4, 10, 30)).json_body["id"]
    assert api.post(f"/tracking/sessions/{sid}/split/", {"at": iso(ist(4, 11))}).json_body["error"]["code"] == "outside"
    assert (
        api.post(f"/tracking/sessions/{sid}/split/", {"at": iso(ist(4, 9, 0) + timedelta(seconds=30))}).status_code
        == 400
    )
    p, _ = services.record_session(
        USER, source="pomodoro", started_at=ist(3, 9), ended_at=ist(3, 9, 25), focus_seconds=1500
    )
    assert (
        api.post(f"/tracking/sessions/{p.id}/split/", {"at": iso(ist(3, 9, 10))}).json_body["error"]["code"]
        == "pomodoro_fixed"
    )


def test_another_students_sessions_are_never_found(api, other_api):
    sid = manual(api, ist(4, 9), ist(4, 10)).json_body["id"]
    assert other_api.get(f"/tracking/sessions/{sid}/").status_code == 404
    assert other_api.patch(f"/tracking/sessions/{sid}/", {"note": "x"}).status_code == 404
    assert other_api.delete(f"/tracking/sessions/{sid}/").status_code == 404
    assert other_api.post(f"/tracking/sessions/{sid}/split/", {"at": iso(ist(4, 9, 30))}).status_code == 404
    assert other_api.get("/tracking/sessions/").json_body["results"] == []
    token = api.delete(f"/tracking/sessions/{manual(api, ist(3, 9), ist(3, 10)).json_body['id']}/").json_body[
        "undo_token"
    ]
    assert other_api.post("/tracking/sessions/undo/", {"undo_token": token}).status_code == 404
    assert other_api.post("/tracking/sessions/merge/", {"session_ids": [sid, sid, str(uuid.uuid4())]}).status_code in (
        400,
        404,
    )


def test_live_captured_rows_cannot_overlap_each_other(api):
    services.record_session(USER, source="stopwatch", started_at=ist(4, 9), ended_at=ist(4, 10), focus_seconds=3600)
    with pytest.raises(services.ConflictError) as e:
        services.record_session(
            USER, source="pomodoro", started_at=ist(4, 9, 30), ended_at=ist(4, 9, 55), focus_seconds=1500
        )
    assert e.value.code == "overlap"
    s, _ = services.record_session(
        USER, source="stopwatch", started_at=ist(4, 8), ended_at=ist(4, 8, 30), focus_seconds=1800
    )
    assert s.overlaps_other is False


def test_finished_time_reaches_coverage_once_per_session(api, ids, scheme):
    enrol = api.post(
        "/coverage/enrollments/",
        {
            "scheme": str(scheme.id),
            "target_term": str(
                __import__("modules.syllabus.models", fromlist=["ExamTerm"])
                .ExamTerm.objects.get(level__course__code="ca", level__code="intermediate", code="2027-05")
                .id
            ),
        },
    )
    assert enrol.status_code == 201, enrol.json_body
    sid = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).json_body["id"]
    progress = ChapterProgress.objects.get(user_id=USER, chapter_id=ids["gst"])
    assert progress.total_study_seconds == 3600 and progress.last_studied_at is not None
    assert CoverageEvent.objects.filter(user_id=USER, type="study_time", source="tracking").count() == 1
    services._forward_to_coverage(StudySession.objects.get(pk=sid))  # a repeat forward is a no-op
    assert CoverageEvent.objects.filter(type="study_time").count() == 1
    ChapterProgress.objects.get(pk=progress.pk).refresh_from_db()
    assert ChapterProgress.objects.get(pk=progress.pk).total_study_seconds == 3600


def test_time_on_a_chapter_the_student_is_not_enrolled_in_is_still_saved(api, ids):
    res = manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"])  # no enrolment at all
    assert res.status_code == 201 and not CoverageEvent.objects.exists()


def test_coverage_failures_never_block_saving(api, ids, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("coverage down")

    monkeypatch.setattr(services.coverage, "record_event", boom)
    assert manual(api, ist(4, 9), ist(4, 10), chapter_id=ids["gst"]).status_code == 201


def test_rollups_always_equal_the_sum_of_sessions_after_a_random_run_of_edits(api):
    import random

    rng = random.Random(7)
    sessions: list[str] = []
    for step in range(60):
        action = rng.choice(["add", "add", "edit", "delete", "merge", "split"]) if sessions else "add"
        day = rng.randint(1, 4)
        if action == "add":
            hour = rng.randint(0, 20)
            res = manual(api, ist(day, hour, rng.choice([0, 15, 40])), minutes=rng.randint(2, 200), on_overlap="keep")
            if res.status_code == 201:
                sessions.append(res.json_body["id"])
        elif action == "edit":
            sid = rng.choice(sessions)
            api.patch(
                f"/tracking/sessions/{sid}/",
                {"ended_at": iso(ist(day, 23, 30) + timedelta(minutes=rng.randint(0, 150)))},
            )
        elif action == "delete":
            sid = rng.choice(sessions)
            if api.delete(f"/tracking/sessions/{sid}/").status_code == 200:
                sessions.remove(sid)
        elif action == "merge" and len(sessions) >= 2:
            pair = rng.sample(sessions, 2)
            res = api.post("/tracking/sessions/merge/", {"session_ids": pair, "subject_id": None, "chapter_id": None})
            if res.status_code == 201:
                sessions = [s for s in sessions if s not in pair] + [res.json_body["session"]["id"]]
        elif action == "split":
            sid = rng.choice(sessions)
            row = StudySession.objects.get(pk=sid)
            res = api.post(
                f"/tracking/sessions/{sid}/split/", {"at": iso(row.started_at + (row.ended_at - row.started_at) / 2)}
            )
            if res.status_code == 201:
                sessions.extend(s["id"] for s in res.json_body["sessions"] if s["id"] not in sessions)
        total = sum(StudySession.objects.values_list("focus_seconds", flat=True))
        assert sum(DailyRollup.objects.values_list("seconds", flat=True)) == total, f"step {step} {action}"
        assert sum(HourBucket.objects.values_list("seconds", flat=True)) == total, f"step {step} {action}"
        assert sum(DailyRollup.objects.values_list("sessions", flat=True)) == StudySession.objects.count()
