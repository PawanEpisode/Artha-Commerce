"""AI "Improve this page" over HTTP and through the worker: gates, consent, price per page, refunds, never downgrade."""
# ruff: noqa: F811 - pytest fixtures imported from the support modules are redefined as test arguments

import json

import pytest
from django.utils import timezone

from core import jobs as core_jobs
from integrations import gemini
from modules.coverage.tests.conftest import USER
from modules.notes.models import AiJob, FilePage, MonthlyUsage, QuotaPlan
from modules.notes.services import ai_ocr
from modules.notes.worker import page_image

from .ai_support import agree, ai_on, gemini_fake  # noqa: F401
from .ocr_export_support import fake_storage, scanned_document  # noqa: F401

pytestmark = pytest.mark.django_db
URL = "/notes/documents/{}/ocr/"
PAGE_TEXT = json.dumps({"text": "Section 16 allows input tax credit.", "legibility": "clear"})


def used(user=USER) -> int:
    row = MonthlyUsage.objects.filter(user_id=user).first()
    return row.ai_ocr_pages if row else 0


def run_worker():
    return core_jobs.run_pending(types=["notes.ocr_ai"], worker="test")


@pytest.fixture
def paid(db):
    QuotaPlan.objects.filter(plan_code="free").update(ai_ocr_pages_per_month=20)


@pytest.fixture
def pictures(monkeypatch):
    """No PDFium: every page renders to the same tiny picture."""
    monkeypatch.setattr(page_image, "render_page_jpeg", lambda path, number: b"\xff\xd8jpeg")


@pytest.fixture
def scan(fake_storage, tmp_path):
    return scanned_document(fake_storage, USER, tmp_path, pages=4)


@pytest.fixture
def ready(api, ai_on, gemini_fake, paid, pictures, scan):  # noqa: ARG001
    assert agree(api).status_code == 200
    gemini_fake.reply = PAGE_TEXT
    return api


def ask(api, doc, pages="1-2"):
    return api.post(URL.format(doc.id), {"mode": "ai", "pages": pages})


def test_it_is_off_until_every_gate_is_open(api, scan, paid):
    assert ask(api, scan).status_code == 403  # PostHog flag unset: fails closed


def test_it_needs_consent_and_a_paid_plan(api, scan, ai_on, gemini_fake, pictures):
    res = ask(api, scan)
    assert (res.status_code, res.json_body["error"]["code"]) == (403, "ai_not_consented")
    agree(api)
    res = ask(api, scan)  # the free plan has 0 AI pages
    assert (res.status_code, res.json_body["error"]["code"]) == (429, "quota_exceeded")
    assert res.json_body["error"]["details"]["kind"] == "ai_ocr_pages"
    assert used() == 0 and not AiJob.objects.exists() and not gemini_fake.calls


def test_the_pages_are_charged_up_front_read_one_by_one_and_stored_above_tesseract(api, ready, scan, gemini_fake):
    FilePage.objects.create(content_id=scan.content_id, page=1, text="credt tax", text_source="ocr", ocr_conf=41)
    res = ask(api, scan)
    assert res.status_code == 202, res.json_body
    body = res.json_body
    assert body["charged_pages"] == 2 and body["job"]["status"] == "queued" and body["estimate_seconds"] == 16
    assert used() == 2
    assert run_worker() == 1
    assert len(gemini_fake.calls) == 2
    pages = {p.page: p for p in FilePage.objects.filter(content_id=scan.content_id)}
    assert (pages[1].text_source, pages[1].ocr_conf, pages[1].text) == ("ai", 92, "Section 16 allows input tax credit.")
    assert pages[2].text_source == "ai"
    got = api.get(f"/notes/ai/ocr/{body['job']['id']}/").json_body
    assert got["status"] == "accepted" and got["done"] == {"1": "clear", "2": "clear"} and got["failed"] == {}
    assert "text" not in json.dumps(got)  # the job never carries page text
    assert AiJob.objects.get(pk=body["job"]["id"]).cost_paise > 0
    assert used() == 2  # nothing is given back for pages that were read


def test_pages_with_text_of_their_own_or_already_read_are_skipped_and_not_charged(api, ready, scan):
    FilePage.objects.create(content_id=scan.content_id, page=1, text="x" * 40, text_source="native")
    FilePage.objects.create(content_id=scan.content_id, page=2, text="read before", text_source="ai", ocr_conf=92)
    res = ask(api, scan, "1-3")
    body = res.json_body
    assert res.status_code == 202 and body["charged_pages"] == 1
    assert body["skipped"] == {"already_read": [2], "has_text": [1], "in_progress": []}
    assert used() == 1
    again = ask(api, scan, "1-3")  # page 3 is in progress now, 1 and 2 are skipped: nothing to do, nothing charged
    assert (
        again.status_code == 200 and again.json_body["job"] is None and again.json_body["skipped"]["in_progress"] == [3]
    )
    assert used() == 1


def test_a_request_with_nothing_for_ai_to_do_is_refused(api, ready, scan):
    FilePage.objects.create(content_id=scan.content_id, page=1, text="x" * 40, text_source="native")
    res = ask(api, scan, "1")
    assert (res.status_code, res.json_body["error"]["code"]) == (422, "not_scanned_or_no_pages")


def test_at_most_ten_pages_a_request_and_a_page_list_is_required(api, ready, scan):
    assert ask(api, scan, "1-99").json_body["error"]["code"] == "invalid_pages"
    assert api.post(URL.format(scan.id), {"mode": "ai"}).json_body["error"]["code"] == "invalid_pages"


def test_a_page_that_cannot_be_read_is_given_back_and_the_others_are_kept(api, ready, scan, monkeypatch):
    replies = iter([PAGE_TEXT, json.dumps({"text": "scribble", "legibility": "poor"})])

    def scripted(prompt, **kwargs):
        return gemini.GeminiResult(text=next(replies), input_tokens=1500, output_tokens=300, model="gemini-test")

    monkeypatch.setattr(gemini, "generate_structured", scripted)
    res = ask(api, scan)
    assert used() == 2
    run_worker()
    job = AiJob.objects.get(pk=res.json_body["job"]["id"])
    assert job.status == "accepted" and job.result_json["done"] == {"1": "clear"}
    assert job.result_json["failed"] == {"2": "illegible"}
    assert used() == 1 and job.scope["refunded_pages"] == [2] and job.charged is True
    assert FilePage.objects.filter(content_id=scan.content_id, text_source="ai").count() == 1


def test_when_nothing_could_be_read_the_job_fails_and_everything_is_given_back(api, ready, scan, gemini_fake):
    gemini_fake.reply = gemini.GeminiBlocked("blocked")
    res = ask(api, scan)
    run_worker()
    job = AiJob.objects.get(pk=res.json_body["job"]["id"])
    assert (job.status, job.error_code, job.charged) == ("failed", "blocked", False)
    assert used() == 0 and not FilePage.objects.filter(text_source="ai").exists()


def test_a_network_error_is_retried_then_given_back_on_the_last_attempt(api, ready, scan, gemini_fake):
    gemini_fake.reply = gemini.GeminiError("down")
    res = ask(api, scan)
    run_worker()  # attempt 1: raises, progress kept, the queue retries
    job = AiJob.objects.get(pk=res.json_body["job"]["id"])
    assert job.status == "running" and used() == 2
    from core.models import Job

    Job.objects.filter(type="notes.ocr_ai").update(run_after=timezone.now())
    core_jobs.run_pending(types=["notes.ocr_ai"], worker="test")
    job.refresh_from_db()
    assert job.status == "failed" and job.error_code == "model_error" and used() == 0


def test_withdrawing_consent_stops_the_job_and_gives_back_the_pages_not_yet_read(api, ready, scan, gemini_fake):
    res = ask(api, scan)
    gemini_fake.on_call = lambda: api.delete("/notes/ai/consent/withdraw/")  # withdrawn while page 1 is being read
    run_worker()
    job = AiJob.objects.get(pk=res.json_body["job"]["id"])
    assert job.status == "cancelled" and job.error_code == "consent_withdrawn"
    assert used() == 0 and not FilePage.objects.filter(text_source="ai").exists()


def test_tesseract_never_overwrites_a_page_ai_has_read(api, ready, scan):
    ask(api, scan, "1")
    run_worker()
    from modules.notes.services import file_pages

    file_pages.upsert_pages(scan.content_id, [file_pages.PageWrite(1, "worse text", "ocr", 30)])
    assert FilePage.objects.get(content_id=scan.content_id, page=1).text_source == "ai"


def test_a_job_is_private_to_the_student_and_the_summary_endpoints_do_not_show_it(api, other_api, ready, scan):
    job_id = ask(api, scan).json_body["job"]["id"]
    assert other_api.get(f"/notes/ai/ocr/{job_id}/").status_code == 404
    assert api.get(f"/notes/ai/summary/{job_id}/").status_code == 404
    assert api.post(f"/notes/ai/summary/{job_id}/cancel/").status_code == 404
    assert AiJob.objects.get(pk=job_id).status == "queued"


def test_a_queued_read_can_be_cancelled_and_gives_the_pages_back(api, ready, scan):
    job_id = ask(api, scan).json_body["job"]["id"]
    assert api.post(f"/notes/ai/ocr/{job_id}/cancel/").json_body["status"] == "cancelled"
    assert used() == 0


def test_the_kill_switch_stops_a_running_job_before_the_next_page(api, ready, scan, settings, gemini_fake):
    job_id = ask(api, scan).json_body["job"]["id"]
    gemini_fake.on_call = lambda: setattr(settings, "NOTES_AI_OCR_ENABLED", False)
    run_worker()
    job = AiJob.objects.get(pk=job_id)
    assert job.status == "accepted" and list(job.result_json["done"]) == ["1"] and used() == 1


def test_every_page_goes_to_google_as_a_picture_with_the_fixed_prompt(api, ready, scan, gemini_fake):
    ask(api, scan, "1")
    run_worker()
    call = gemini_fake.calls[0]
    assert call["image"] == (b"\xff\xd8jpeg", "image/jpeg") and call["system"] == ai_ocr.domain.SYSTEM
    assert "tax credit" not in call["system"].lower()


def test_when_every_page_is_unreadable_the_job_fails_with_a_stored_error_code(api, ready, scan, gemini_fake):
    gemini_fake.reply = json.dumps({"text": "scribble", "legibility": "poor"})
    res = ask(api, scan)
    run_worker()
    job = AiJob.objects.get(pk=res.json_body["job"]["id"])
    assert (job.status, job.error_code, job.charged) == ("failed", "too_little", False)
    assert set(job.result_json["failed"].values()) == {"illegible"} and used() == 0
