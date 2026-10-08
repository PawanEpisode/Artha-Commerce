"""AI exam summary over HTTP and through the worker: gates, consent, quota, cache, refunds, review and the take-backs."""
# ruff: noqa: F811 - pytest fixtures imported from the support modules are redefined as test arguments

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from core import jobs as core_jobs
from core.models import Job
from integrations import gemini
from modules.coverage.tests.conftest import OTHER, USER
from modules.notes.domain import ai_consent
from modules.notes.models import AiJob, MonthlyUsage, Note, QuotaPlan
from modules.notes.services import ai_jobs, summary

from .ai_support import agree, ai_on, gemini_fake, good_reply, post_summary, seed_chapter  # noqa: F401
from .conftest import new_note

pytestmark = pytest.mark.django_db


def used(user=USER) -> int:
    row = MonthlyUsage.objects.filter(user_id=user).first()
    return row.ai_summaries if row else 0


def run_worker():
    return core_jobs.run_pending(types=["notes.summarize"], worker="test")


@pytest.fixture
def ready(api, chapter, ai_on, gemini_fake):
    """A student who agreed, with material on the chapter."""
    seed_chapter(api, chapter, USER)
    assert agree(api).status_code == 200
    return api


def request_and_run(api, chapter):
    res = post_summary(api, chapter)
    assert res.status_code == 202, res.json_body
    run_worker()
    return api.get(f"/notes/ai/summary/{res.json_body['id']}/").json_body


# --- gates -------------------------------------------------------------------------------------------------------------
def test_without_the_notes_ai_flag_every_ai_route_is_403_feature_disabled(api, chapter, settings):
    settings.GEMINI_API_KEY = "k"  # no PostHog key: notes_ai fails CLOSED, unlike notes and notes_pdf
    for method, path in [
        ("get", "/notes/ai/consent/"),
        ("put", "/notes/ai/consent/"),
        ("post", "/notes/ai/summary/"),
        ("get", f"/notes/ai/summary/{uuid.uuid4()}/"),
        ("post", f"/notes/ai/summary/{uuid.uuid4()}/accept/"),
    ]:
        res = api._send(method, path, {} if method != "get" else None)
        assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled", path


@pytest.mark.parametrize(
    "setting,value",
    [
        ("GEMINI_API_KEY", ""),
        ("GEMINI_DATA_TIER", "unconfirmed"),
        ("GEMINI_DATA_TIER", "free"),
        ("NOTES_AI_CONSENT_APPROVED", ""),
        ("NOTES_AI_CONSENT_APPROVED", "2020-old"),
        ("NOTES_AI_DAILY_BUDGET_PAISE", 0),
    ],
)
def test_ai_stays_off_until_every_owner_gate_is_open(api, chapter, ai_on, gemini_fake, settings, setting, value):
    seed_chapter(api, chapter, USER)
    setattr(settings, setting, value)
    assert api.get("/notes/ai/consent/").json_body["available"] is False
    assert agree(api).status_code == 503
    assert post_summary(api, chapter).status_code == 503
    assert not gemini_fake.calls and used() == 0 and not AiJob.objects.exists()


def test_the_summary_kill_switch_refuses_new_requests_but_keeps_consent_available_for_ocr(
    api, chapter, ai_on, gemini_fake, settings
):
    seed_chapter(api, chapter, USER)
    agree(api)
    settings.NOTES_AI_SUMMARY_ENABLED = False
    assert post_summary(api, chapter).status_code == 503
    assert not gemini_fake.calls and used() == 0


# --- consent -----------------------------------------------------------------------------------------------------------
def test_the_consent_text_is_served_with_its_version(api, ai_on):
    body = api.get("/notes/ai/consent/").json_body
    assert body["consented"] is False and body["available"] is True
    assert body["text"]["version"] == ai_consent.VERSION and len(body["text"]["points"]) >= 4
    assert "never sent" in " ".join(p["text"] for p in body["text"]["points"])  # the PDF itself is not sent


def test_consent_is_recorded_with_the_version_the_student_saw(api, ai_on):
    assert api.put("/notes/ai/consent/", {"version": "2019-old"}).status_code == 409
    res = agree(api)
    assert res.status_code == 200 and res.json_body["consented"] and res.json_body["version"] == ai_consent.VERSION
    assert res.json_body["consented_at"]


def test_a_request_without_consent_is_refused_and_costs_nothing(api, chapter, ai_on, gemini_fake):
    seed_chapter(api, chapter, USER)
    res = post_summary(api, chapter)
    assert res.status_code == 403 and res.json_body["error"]["code"] == "ai_not_consented"
    assert res.json_body["error"]["details"]["version"] == ai_consent.VERSION
    assert used() == 0 and not AiJob.objects.exists() and not gemini_fake.calls


def test_a_new_consent_version_asks_everyone_again(ready, chapter, monkeypatch):
    monkeypatch.setattr(ai_consent, "VERSION", "2099-v2")
    from django.conf import settings

    settings.NOTES_AI_CONSENT_APPROVED = "2099-v2"
    res = post_summary(ready, chapter)
    assert res.status_code == 403 and res.json_body["error"]["code"] == "ai_not_consented"


# --- the request -------------------------------------------------------------------------------------------------------
def test_a_request_charges_one_summary_queues_a_job_and_stores_ids_only(ready, chapter):
    res = post_summary(ready, chapter)
    assert res.status_code == 202, res.json_body
    body = res.json_body
    assert body["status"] == "queued" and body["item_count"] == 4 and body["estimate_seconds"] >= 15
    assert body["cached"] is False and body["draft"] is None and used() == 1
    job = Job.objects.get(type="notes.summarize")
    assert job.payload == {"job_id": body["id"]} and job.max_attempts == summary.MAX_ATTEMPTS
    row = AiJob.objects.get(pk=body["id"])
    assert row.charged and row.prompt_version == "notes.summary.v1" and row.model == "gemini-test"
    assert all(set(i) == {"kind", "id"} for i in row.scope["items"])  # no student text in the stored scope


def test_a_replayed_client_id_returns_the_same_job_and_charges_nothing_more(ready, chapter):
    cid = str(uuid.uuid4())
    first = ready.post("/notes/ai/summary/", {"client_id": cid, "chapter_id": str(chapter.id)})
    again = ready.post("/notes/ai/summary/", {"client_id": cid, "chapter_id": str(chapter.id)})
    assert (first.status_code, again.status_code) == (202, 200) and first.json_body["id"] == again.json_body["id"]
    assert used() == 1 and AiJob.objects.count() == 1


def test_not_enough_material_is_422_and_free(api, chapter, ai_on, gemini_fake):
    new_note(api, "Short.", chapter_id=str(chapter.id))
    agree(api)
    res = post_summary(api, chapter)
    assert res.status_code == 422 and res.json_body["error"]["code"] == "not_enough_material"
    assert res.json_body["error"]["details"]["min_items"] == 3 and used() == 0


def test_an_unknown_chapter_is_422(ready):
    res = ready.post("/notes/ai/summary/", {"client_id": str(uuid.uuid4()), "chapter_id": str(uuid.uuid4())})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "unknown_chapter" and used() == 0


def test_only_the_students_own_material_is_used(ready, other_api, chapter):
    new_note(other_api, "SECRET of another student " * 30, chapter_id=str(chapter.id))
    post_summary(ready, chapter)
    run_worker()
    sent = " ".join(c["prompt"] for c in ready_calls(ready))
    assert "SECRET" not in sent


def ready_calls(_api):
    from integrations import gemini as g

    return g.generate_structured.calls


def test_include_can_limit_the_inputs_to_notes(ready, chapter):
    res = post_summary(ready, chapter, include=["notes"])
    assert res.status_code == 422  # two notes alone are below the minimum of three items
    res = post_summary(ready, chapter, include=["highlights"])
    assert res.status_code == 422


def test_the_monthly_quota_is_enforced_with_the_reset_date_and_nothing_is_queued(ready, chapter):
    QuotaPlan.objects.filter(plan_code="free").update(ai_summaries_per_month=1)
    request_and_run(ready, chapter)  # the first summary is done, so the chapter is not busy any more
    new_note(ready, "Another long note on the chapter. " * 20, chapter_id=str(chapter.id))
    res = post_summary(ready, chapter)
    assert res.status_code == 429 and res.json_body["error"]["code"] == "quota_exceeded"
    details = res.json_body["error"]["details"]
    assert details["kind"] == "ai_summaries" and details["used"] == 1 and details["limit"] == 1 and details["resets_on"]
    assert used() == 1 and AiJob.objects.count() == 1 and Job.objects.filter(type="notes.summarize").count() == 1


def test_a_second_request_for_a_busy_chapter_joins_the_running_one(ready, chapter):
    first = post_summary(ready, chapter)
    new_note(ready, "A late extra note about credit. " * 20, chapter_id=str(chapter.id))
    second = post_summary(ready, chapter)
    assert second.status_code == 200 and second.json_body["id"] == first.json_body["id"] and used() == 1


def test_the_daily_budget_blocks_new_jobs_and_charges_nothing(ready, chapter, settings):
    settings.NOTES_AI_DAILY_BUDGET_PAISE = 100  # less than the reserve for one summary
    res = post_summary(ready, chapter)
    assert res.status_code == 503 and res.json_body["error"]["code"] == "ai_budget_exhausted"
    assert used() == 0 and not AiJob.objects.exists()


# --- the worker --------------------------------------------------------------------------------------------------------
def test_the_worker_stores_a_draft_with_sources_and_costs(ready, chapter, gemini_fake, capture_events):
    seen = capture_events("notes_summary_ready")
    job = request_and_run(ready, chapter)
    assert job["status"] == "ready" and job["expires_at"]
    draft = job["draft"]
    assert draft["title"] == "GST: input tax credit" and "## When ITC is allowed" in draft["body_md"]
    assert len(draft["sources"]) == 3 and {s["kind"] for s in draft["sources"]} <= {"note", "highlight"}
    row = AiJob.objects.get(pk=job["id"])
    assert (row.input_tokens, row.output_tokens, row.cost_paise) == (2000, 400, 59)  # 26.4 + 31.68 paise, rounded up
    assert seen and set(seen[0]) >= {"user_id", "job_id", "items", "cost_paise"} and "body" not in str(seen[0])
    prompt = gemini_fake.calls[0]["prompt"]
    assert "Credit is blocked for motor vehicles" in prompt and "Study PDF" not in prompt
    assert gemini_fake.calls[0]["system"].startswith("You write exam revision summaries")


def test_regenerating_unchanged_inputs_returns_the_earlier_draft_for_free(ready, chapter, gemini_fake):
    first = request_and_run(ready, chapter)
    again = post_summary(ready, chapter)
    assert again.status_code == 200 and again.json_body["cached"] is True and again.json_body["id"] == first["id"]
    assert used() == 1 and len(gemini_fake.calls) == 1


def test_changing_a_note_makes_the_next_request_a_new_paid_job(ready, chapter, gemini_fake):
    first = request_and_run(ready, chapter)
    note = Note.objects.filter(user_id=USER, kind="note").first()
    ready.patch(f"/notes/notes/{note.id}/", {"base_rev": note.rev, "body_md": "Rewritten body. " * 40})
    again = post_summary(ready, chapter)
    assert again.status_code == 202 and again.json_body["id"] != first["id"] and used() == 2


def test_a_blocked_answer_fails_the_job_and_refunds(ready, chapter, gemini_fake):
    gemini_fake.reply = gemini.GeminiBlocked("blocked")
    job = request_and_run(ready, chapter)
    assert job["status"] == "failed" and job["error_code"] == "blocked" and job["charged"] is False and used() == 0


def test_a_bad_answer_fails_the_job_and_refunds(ready, chapter, gemini_fake):
    gemini_fake.reply = "this is not json"
    job = request_and_run(ready, chapter)
    assert job["status"] == "failed" and job["error_code"] == "model_error" and used() == 0


def test_an_answer_with_no_real_sources_is_too_little_and_refunds(ready, chapter, gemini_fake):
    gemini_fake.reply = good_reply(sources=[91, 92, 93])
    job = request_and_run(ready, chapter)
    assert job["error_code"] == "too_little" and used() == 0


def test_a_network_error_is_retried_and_only_the_last_attempt_fails_and_refunds(ready, chapter, gemini_fake):
    gemini_fake.reply = gemini.GeminiError("boom")
    jid = post_summary(ready, chapter).json_body["id"]
    row = Job.objects.get(type="notes.summarize")
    with pytest.raises(gemini.GeminiError):
        summary.run_summary(row.payload)  # not the last attempt: the queue retries, nothing refunded
    assert AiJob.objects.get(pk=jid).status == "running" and used() == 1
    run_worker()
    run_worker()
    Job.objects.filter(pk=row.pk).update(run_after=timezone.now() - timedelta(seconds=1))
    run_worker()
    assert AiJob.objects.get(pk=jid).status == "failed" and used() == 0 and len(gemini_fake.calls) >= 2


def test_a_job_the_queue_gave_up_on_is_closed_and_refunded(ready, chapter):
    jid = post_summary(ready, chapter).json_body["id"]
    summary.give_up({"job_id": jid})
    row = AiJob.objects.get(pk=jid)
    assert row.status == "failed" and row.error_code == "model_error" and used() == 0


def test_the_kill_switch_cancels_queued_jobs_in_the_worker_and_refunds(ready, chapter, settings, gemini_fake):
    jid = post_summary(ready, chapter).json_body["id"]
    settings.NOTES_AI_SUMMARY_ENABLED = False
    run_worker()
    row = AiJob.objects.get(pk=jid)
    assert row.status == "cancelled" and row.error_code == "unavailable" and used() == 0 and not gemini_fake.calls


def test_consent_withdrawn_before_the_worker_runs_cancels_and_refunds(ready, chapter, gemini_fake):
    jid = post_summary(ready, chapter).json_body["id"]
    res = ready.delete("/notes/ai/consent/withdraw/")
    assert res.status_code == 200 and res.json_body["requests_cancelled"] == 1
    run_worker()
    row = AiJob.objects.get(pk=jid)
    assert row.status == "cancelled" and used() == 0 and not gemini_fake.calls


def test_consent_withdrawn_while_the_model_runs_keeps_nothing(ready, chapter, gemini_fake):
    gemini_fake.on_call = lambda: ready.delete("/notes/ai/consent/withdraw/")
    jid = post_summary(ready, chapter).json_body["id"]
    run_worker()
    row = AiJob.objects.get(pk=jid)
    assert row.status == "cancelled" and row.error_code == "consent_withdrawn" and row.result_md is None and used() == 0


def test_withdrawing_deletes_drafts_but_keeps_accepted_summaries(ready, chapter):
    job = request_and_run(ready, chapter)
    assert ready.delete("/notes/ai/consent/withdraw/").json_body["drafts_deleted"] == 1
    row = AiJob.objects.get(pk=job["id"])
    assert row.status == "discarded" and row.result_md is None and row.result_json is None
    assert ready.get("/notes/ai/consent/").json_body["consented"] is False
    assert post_summary(ready, chapter).status_code == 403


def test_withdrawing_works_with_every_flag_off(api, chapter):
    assert api.delete("/notes/ai/consent/withdraw/").status_code == 200  # no notes_ai, no AI set up: still allowed


# --- review: accept, discard, cancel -----------------------------------------------------------------------------------
def test_accepting_creates_the_current_exam_summary_note_with_its_sources(ready, chapter, level_id):
    job = request_and_run(ready, chapter)
    res = ready.post(f"/notes/ai/summary/{job['id']}/accept/", {})
    assert res.status_code == 200, res.json_body
    note = res.json_body["note"]
    assert note["kind"] == "exam_summary" and note["origin"] == "ai_summary" and note["is_current_summary"] is True
    assert note["title"] == "GST: input tax credit" and note["link"]["chapter_key"] == "gst-itc"
    assert "## Sources" in note["body_md"]
    row = Note.objects.get(pk=note["id"])
    assert row.ai_job_id and len(row.source_refs) == 3
    after = AiJob.objects.get(pk=job["id"])
    assert after.status == "accepted" and after.result_md is None and after.result_json is None
    assert str(after.result_note_id) == note["id"]
    overview = ready.get(f"/notes/chapters/gst-itc/overview/?level={level_id}&subject=taxation").json_body
    assert overview["has_summary"] is True and overview["current_summary"]["id"] == note["id"]


def test_accepting_twice_returns_the_same_note(ready, chapter):
    job = request_and_run(ready, chapter)
    a = ready.post(f"/notes/ai/summary/{job['id']}/accept/", {}).json_body["note"]["id"]
    b = ready.post(f"/notes/ai/summary/{job['id']}/accept/", {}).json_body["note"]["id"]
    assert a == b and Note.objects.filter(kind="exam_summary").count() == 1


def test_the_students_edit_is_what_gets_saved(ready, chapter):
    job = request_and_run(ready, chapter)
    res = ready.post(
        f"/notes/ai/summary/{job['id']}/accept/", {"title": "My GST summary", "body_md": "## Mine\n\n- Edited point"}
    )
    note = res.json_body["note"]
    assert note["title"] == "My GST summary" and note["body_md"].startswith("## Mine")


def test_an_edit_that_breaks_the_note_rules_is_422_and_keeps_the_draft(ready, chapter):
    job = request_and_run(ready, chapter)
    res = ready.post(f"/notes/ai/summary/{job['id']}/accept/", {"body_md": f"![x](attachment:{uuid.uuid4()})"})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "invalid_body"
    assert AiJob.objects.get(pk=job["id"]).status == "ready"


def test_a_newer_summary_takes_over_as_current(ready, chapter, gemini_fake):
    first = request_and_run(ready, chapter)
    old = ready.post(f"/notes/ai/summary/{first['id']}/accept/", {}).json_body["note"]["id"]
    new_note(ready, "One more long note about eligibility. " * 20, chapter_id=str(chapter.id))
    second = request_and_run(ready, chapter)
    new = ready.post(f"/notes/ai/summary/{second['id']}/accept/", {}).json_body["note"]["id"]
    assert Note.objects.get(pk=old).is_current_summary is False and Note.objects.get(pk=new).is_current_summary


def test_a_draft_that_is_not_ready_cannot_be_accepted(ready, chapter):
    jid = post_summary(ready, chapter).json_body["id"]
    res = ready.post(f"/notes/ai/summary/{jid}/accept/", {})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "not_ready"


def test_discarding_keeps_nothing_and_does_not_refund(ready, chapter):
    job = request_and_run(ready, chapter)
    res = ready.post(f"/notes/ai/summary/{job['id']}/discard/", {})
    assert res.status_code == 200 and res.json_body["status"] == "discarded" and res.json_body["draft"] is None
    assert ready.post(f"/notes/ai/summary/{job['id']}/discard/", {}).status_code == 200  # idempotent
    row = AiJob.objects.get(pk=job["id"])
    assert row.result_md is None and used() == 1 and not Note.objects.filter(kind="exam_summary").exists()


def test_cancelling_a_queued_request_refunds_it_but_a_running_one_cannot_be_cancelled(ready, chapter):
    jid = post_summary(ready, chapter).json_body["id"]
    assert ready.post(f"/notes/ai/summary/{jid}/cancel/", {}).json_body["status"] == "cancelled" and used() == 0
    assert ready.post(f"/notes/ai/summary/{jid}/cancel/", {}).status_code == 200  # idempotent, refunded once
    assert used() == 0
    new_note(ready, "A different long note for a new request. " * 20, chapter_id=str(chapter.id))
    j2 = post_summary(ready, chapter).json_body["id"]
    AiJob.objects.filter(pk=j2).update(status="running")
    res = ready.post(f"/notes/ai/summary/{j2}/cancel/", {})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "not_cancellable"


def test_the_latest_active_or_ready_job_of_a_chapter_can_be_found_to_resume(ready, chapter):
    assert ready.get(f"/notes/ai/summary/?chapter_id={chapter.id}").json_body == {"job": None}
    job = request_and_run(ready, chapter)
    found = ready.get(f"/notes/ai/summary/?chapter_id={chapter.id}").json_body["job"]
    assert found["id"] == job["id"] and found["draft"]["title"]


# --- isolation and data rights -----------------------------------------------------------------------------------------
def test_another_student_gets_404_for_every_job_route(ready, other_api, chapter):
    job = request_and_run(ready, chapter)
    for method, suffix in [("get", ""), ("post", "accept/"), ("post", "discard/"), ("post", "cancel/")]:
        res = other_api._send(method, f"/notes/ai/summary/{job['id']}/{suffix}", {} if method == "post" else None)
        assert res.status_code in (404, 403), (method, suffix)
        assert res.status_code == 404 or res.json_body["error"]["code"] == "feature_disabled"
    assert AiJob.objects.get(pk=job["id"]).status == "ready"


def test_the_other_student_never_sees_my_draft_even_with_notes_ai_on(ready, ai_on, chapter, make_token):
    from modules.tracking.tests.conftest import Api

    job = request_and_run(ready, chapter)
    stranger = Api(make_token(sub=OTHER))
    res = stranger.get(f"/notes/ai/summary/{job['id']}/")
    assert res.status_code == 404


def test_drafts_expire_after_fourteen_days_and_the_text_is_deleted(ready, chapter):
    job = request_and_run(ready, chapter)
    AiJob.objects.filter(pk=job["id"]).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert ai_jobs.expire_drafts() == 1
    row = AiJob.objects.get(pk=job["id"])
    assert row.status == "expired" and row.result_md is None and row.result_json is None


def test_the_tick_queues_the_expiry_job(client, settings):
    from modules.notes import jobs

    jobs.tick()
    assert Job.objects.filter(type="notes.expire_ai").exists()


def test_export_lists_requests_without_text_once_a_draft_is_gone_and_delete_all_removes_them(ready, chapter):
    job = request_and_run(ready, chapter)
    ready.post(f"/notes/ai/summary/{job['id']}/discard/", {})
    exported = ready.get("/notes/export/").json_body
    assert [r["id"] for r in exported["ai_requests"]] == [job["id"]] and exported["ai_requests"][0]["result_md"] is None
    report = ready.delete("/notes/").json_body["deleted"]
    assert report["ai_jobs"] == 1 and not AiJob.objects.exists()
