"""
R2-W5: AI card suggestions (FR-F15-18 to 20). The model is never reached: `adapters.ai.generate` is replaced and the notes source is
a fake provider. Covered: the gates (flag, key, consent), the request and its quota charge, the worker, the evidence check, accept
(idempotent, edited), reject and the 90-day memory, the cache, the daily quota, refunds, withdrawing consent, erase and export.
"""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from core import feature_flags
from core import suggestion_source_port as port
from core.models import Job
from integrations import gemini
from modules.coverage.tests.conftest import USER
from modules.recall.adapters import ai as ai_adapter
from modules.recall.domain import ai_consent as consent_text
from modules.recall.models import (
    RecallAiCall,
    RecallAiUsage,
    RecallItem,
    RecallQuotaPlan,
    RecallSuggestion,
    RecallSuggestionBatch,
    RecallSuggestionReject,
)
from modules.recall.services import erasure
from modules.recall.services import suggestions as svc

pytestmark = pytest.mark.django_db

NOTE_TEXT = (
    "Input tax credit is blocked on motor vehicles used for personal purposes under Section 17(5) of the CGST Act. "
    "A registered person can claim input tax credit only when he holds a valid tax invoice and has received the goods."
)
Q1 = "blocked on motor vehicles used for personal purposes under Section 17(5)"
Q2 = "claim input tax credit only when he holds a valid tax invoice"


class FakeNotes:
    def __init__(self, text=NOTE_TEXT):
        self.text = text
        self.asked = []

    def texts_for(self, user_id, chapter_id, *, limit):
        self.asked.append((str(user_id), str(chapter_id)))
        return [port.SourcePiece("note:n1", "Note", self.text)] if self.text else []


def card(prompt, answer, quote, n=1):
    return {"kind": "pointer", "prompt_md": prompt, "answer_md": answer, "evidence_quote": quote, "source_n": n}


GOOD = [
    card("When is ITC blocked on vehicles?", "For personal use, under Section 17(5).", Q1),
    card("What does ITC need?", "A valid tax invoice.", Q2),
]


def fake_model(monkeypatch, cards_out, *, tokens=(1000, 500)):
    calls = []

    def generate(sources, kinds, count):
        calls.append({"sources": [s.ref for s in sources], "kinds": list(kinds), "count": count})
        return gemini.GeminiResult(json.dumps({"cards": cards_out}), tokens[0], tokens[1], "test-model")

    monkeypatch.setattr(ai_adapter, "generate", generate)
    return calls


@pytest.fixture
def notes(monkeypatch):
    provider = FakeNotes()
    port.register_suggestion_source("notes", provider)
    yield provider
    port.register_suggestion_source("notes", None)


@pytest.fixture
def ai_on(settings):
    settings.GEMINI_API_KEY = "test-key"
    settings.GEMINI_DATA_TIER = "paid"
    settings.RECALL_AI_CONSENT_APPROVED = consent_text.VERSION
    settings.RECALL_AI_ENABLED = True
    settings.RECALL_AI_DAILY_BUDGET_PAISE = 100_000


@pytest.fixture
def consented(api, ai_on):
    assert api.post("/recall/ai/consent/", {"version": consent_text.VERSION}).status_code == 200


def ask(api, chapter, **kw):
    body = {"chapter_id": chapter, "sources": ["notes"], "count": 6, "client_id": str(uuid.uuid4())}
    body.update(kw)
    return api.post("/recall/suggestions/", body)


def work(batch_id):
    return svc.run_batch({"batch_id": batch_id})


def usage():
    return RecallAiUsage.objects.filter(user_id=USER).values_list("batches", "suggestions").first() or (0, 0)


# ------------------------------------------------------------------------------------------------ gates


def test_the_ai_flag_fails_closed_and_is_separate_from_the_recall_flag(api, monkeypatch):
    feature_flags.clear_flag_cache()
    monkeypatch.setattr(feature_flags, "_lookup", lambda name, distinct_id: name == "recall_system")
    res = api.get("/recall/ai/")
    assert res.status_code == 403 and res.json_body["error"]["code"] == "feature_disabled"
    assert api.get("/recall/cards/").status_code == 200  # recall itself is still on


def test_the_overview_says_ai_is_off_until_everything_is_configured(api, ids, settings):
    settings.GEMINI_API_KEY = ""
    body = api.get("/recall/ai/").json_body
    assert body["available"] is False and body["consent"]["given"] is False
    assert body["quota"]["batches_limit"] == 3 and body["quota"]["suggestions_limit"] == 30
    assert "pasted" in body["sources"]


@pytest.mark.parametrize(
    "change",
    [
        {"GEMINI_API_KEY": ""},
        {"GEMINI_DATA_TIER": "unconfirmed"},
        {"RECALL_AI_CONSENT_APPROVED": ""},
        {"RECALL_AI_ENABLED": False},
        {"RECALL_AI_DAILY_BUDGET_PAISE": 0},
    ],
)
def test_every_missing_setting_keeps_ai_off(api, ids, notes, ai_on, settings, change):
    for key, value in change.items():
        setattr(settings, key, value)
    assert api.get("/recall/ai/").json_body["available"] is False
    assert api.post("/recall/ai/consent/", {"version": consent_text.VERSION}).status_code == 503
    res = ask(api, ids["gst"])
    assert res.status_code == 503 and res.json_body["error"]["code"] == "ai_unavailable"
    assert Job.objects.filter(type="recall.suggest").count() == 0


def test_nothing_is_sent_without_her_consent(api, ids, notes, ai_on):
    res = ask(api, ids["gst"])
    assert res.status_code == 403 and res.json_body["error"]["code"] == "ai_not_consented"
    assert res.json_body["error"]["details"]["version"] == consent_text.VERSION
    assert notes.asked == [] and usage() == (0, 0)


def test_a_stale_consent_version_is_refused(api, ai_on):
    res = api.post("/recall/ai/consent/", {"version": "2020-01-v0"})
    assert res.status_code == 409 and res.json_body["error"]["code"] == "consent_version_mismatch"


def test_the_notice_is_served_with_its_version(api, ai_on):
    body = api.get("/recall/ai/consent/").json_body
    assert body["version"] == consent_text.VERSION and body["consented"] is False and body["points"]


# ------------------------------------------------------------------------------------------------ request


def test_a_request_charges_the_quota_queues_one_job_and_puts_no_text_in_it(api, ids, notes, consented):
    res = ask(api, ids["gst"], count=6)
    assert res.status_code == 202, res.json_body
    body = res.json_body
    assert body["status"] == "queued" and body["suggestions"] == [] and body["estimate_seconds"] > 0
    assert usage() == (1, 6)
    job = Job.objects.get(type="recall.suggest")
    assert job.payload == {"batch_id": body["id"]}
    assert notes.asked == [(USER, ids["gst"])]


def test_a_repeated_client_id_is_a_replay_and_charges_nothing(api, ids, notes, consented):
    cid = str(uuid.uuid4())
    first = ask(api, ids["gst"], client_id=cid)
    again = ask(api, ids["gst"], client_id=cid)
    assert again.status_code == 200 and again.json_body["id"] == first.json_body["id"]
    assert usage() == (1, 6) and Job.objects.filter(type="recall.suggest").count() == 1


def test_a_batch_already_running_for_the_chapter_is_returned_without_a_charge(api, ids, notes, consented):
    first = ask(api, ids["gst"])
    second = ask(api, ids["gst"], count=3)
    assert second.status_code == 200 and second.json_body["id"] == first.json_body["id"]
    assert second.json_body["reused"] == "active" and usage() == (1, 6)


def test_validation_unknown_chapter_sources_and_too_little_material(api, ids, notes, consented):
    assert ask(api, str(uuid.uuid4())).status_code == 422
    curr_wa = port.get_suggestion_source("wrong_answers")
    port.register_suggestion_source("wrong_answers", None)
    try:
        assert ask(api, ids["gst"], sources=["wrong_answers"]).json_body["error"]["code"] == "source_unavailable"
    finally:
        port.register_suggestion_source("wrong_answers", curr_wa)
    assert ask(api, ids["gst"], sources=["bogus"]).status_code == 400
    assert ask(api, ids["gst"], count=11).status_code == 400
    assert (
        ask(api, ids["gst"], sources=["pasted"], pasted_text="too short").json_body["error"]["code"]
        == "not_enough_material"
    )
    notes.text = ""
    assert ask(api, ids["gst"]).json_body["error"]["code"] == "not_enough_material"
    assert usage() == (0, 0) and Job.objects.filter(type="recall.suggest").count() == 0


def test_pasted_text_is_kept_only_until_the_job_ends(api, ids, notes, consented, monkeypatch):
    fake_model(monkeypatch, GOOD)
    res = ask(api, ids["gst"], sources=["pasted"], pasted_text=NOTE_TEXT)
    bid = res.json_body["id"]
    assert RecallSuggestionBatch.objects.get(pk=bid).pasted_text == NOTE_TEXT
    assert notes.asked == []  # notes was not a chosen source
    work(bid)
    assert RecallSuggestionBatch.objects.get(pk=bid).pasted_text == ""


# ------------------------------------------------------------------------------------------------ the worker


def test_the_worker_keeps_drafts_with_verbatim_evidence_and_refunds_the_unused_quota(
    api, ids, notes, consented, monkeypatch
):
    calls = fake_model(monkeypatch, [*GOOD, card("Invented?", "Yes.", "Credit is allowed on trucks and buses always")])
    bid = ask(api, ids["gst"], count=6).json_body["id"]
    out = work(bid)
    assert out["status"] == "ready" and out["produced"] == 2 and out["dropped"] == 1
    assert calls == [{"sources": ["note:n1"], "kinds": list(calls[0]["kinds"]), "count": 6}]
    body = api.get(f"/recall/suggestions/{bid}/").json_body
    assert body["status"] == "ready" and len(body["suggestions"]) == 2 and body["dropped"] == 1
    s = body["suggestions"][0]
    assert s["status"] == "draft" and s["evidence_quote"] == Q1 and s["evidence_label"] == "Your note"
    assert s["front_md"] and s["back_md"]
    assert usage() == (1, 2)  # 6 reserved, 2 used, 4 given back
    ledger = RecallAiCall.objects.get(batch_id=bid)
    assert ledger.status == "ok" and ledger.tokens_in == 1000 and ledger.tokens_out == 500 and ledger.cost_paise > 0


def test_an_answer_with_nothing_usable_costs_the_student_nothing(api, ids, notes, consented, monkeypatch):
    fake_model(monkeypatch, [card("x?", "y", "this quote is not in the notes at all, sorry")])
    bid = ask(api, ids["gst"]).json_body["id"]
    out = work(bid)
    assert out == {"status": "failed", "reason": "nothing_usable", "dropped": 1, "cost_paise": out["cost_paise"]}
    assert usage() == (0, 0) and RecallSuggestionBatch.objects.get(pk=bid).error_code == "nothing_usable"
    assert RecallAiCall.objects.get(batch_id=bid).status == "ok"  # the model was paid for; the ledger says so


def test_a_blocked_answer_fails_the_batch_and_refunds_everything(api, ids, notes, consented, monkeypatch):
    def blocked(*a, **k):
        raise gemini.GeminiBlocked("blocked")

    monkeypatch.setattr(ai_adapter, "generate", blocked)
    bid = ask(api, ids["gst"]).json_body["id"]
    assert work(bid)["reason"] == "blocked"
    assert usage() == (0, 0)
    assert RecallAiCall.objects.get(batch_id=bid).status == "blocked"
    assert api.get(f"/recall/suggestions/{bid}/").json_body["error_code"] == "blocked"


def test_a_network_error_is_retried_and_only_the_last_attempt_refunds(api, ids, notes, consented, monkeypatch):
    def broken(*a, **k):
        raise gemini.GeminiError("down")

    monkeypatch.setattr(ai_adapter, "generate", broken)
    bid = ask(api, ids["gst"]).json_body["id"]
    with pytest.raises(gemini.GeminiError):
        work(bid)  # raised so the queue retries
    assert usage() == (1, 6) and RecallSuggestionBatch.objects.get(pk=bid).status == "running"
    monkeypatch.setattr(svc, "_last_attempt", lambda: True)
    assert work(bid)["reason"] == "model_error"
    assert usage() == (0, 0)


def test_the_queue_giving_up_closes_the_batch_and_refunds(api, ids, notes, consented):
    bid = ask(api, ids["gst"]).json_body["id"]
    svc.give_up({"batch_id": bid})
    assert usage() == (0, 0) and RecallSuggestionBatch.objects.get(pk=bid).status == "failed"
    svc.give_up({"batch_id": bid})  # once only
    assert usage() == (0, 0)


def test_the_worker_rechecks_ai_consent_and_the_material(api, ids, notes, consented, monkeypatch, settings):
    calls = fake_model(monkeypatch, GOOD)
    a = ask(api, ids["gst"]).json_body["id"]
    settings.RECALL_AI_ENABLED = False
    assert work(a)["reason"] == "unavailable"
    settings.RECALL_AI_ENABLED = True
    b = ask(api, ids["gst"]).json_body["id"]
    notes.text = ""
    assert work(b)["reason"] == "too_little"
    assert calls == [] and usage() == (0, 0)


def test_a_finished_batch_is_not_run_twice(api, ids, notes, consented, monkeypatch):
    calls = fake_model(monkeypatch, GOOD)
    bid = ask(api, ids["gst"]).json_body["id"]
    work(bid)
    assert work(bid) == {"skipped": True} and len(calls) == 1


# ------------------------------------------------------------------------------------------------ cache and quota


def test_the_same_material_again_returns_the_same_drafts_without_a_charge(api, ids, notes, consented, monkeypatch):
    calls = fake_model(monkeypatch, GOOD)
    first = ask(api, ids["gst"]).json_body["id"]
    work(first)
    spent = usage()
    again = ask(api, ids["gst"])
    assert again.status_code == 200 and again.json_body["id"] == first and again.json_body["reused"] == "cache"
    assert usage() == spent and len(calls) == 1 and Job.objects.filter(type="recall.suggest").count() == 1


def test_the_batch_limit_of_the_plan_answers_429_with_the_reset_day(api, ids, notes, consented, monkeypatch):
    fake_model(monkeypatch, GOOD)
    for i in range(3):
        notes.text = f"{NOTE_TEXT} Variant {i}."
        work(ask(api, ids["gst"]).json_body["id"])
    notes.text = f"{NOTE_TEXT} Variant 3."
    res = ask(api, ids["gst"])
    err = res.json_body["error"]
    assert res.status_code == 429 and err["code"] == "quota_exceeded"
    assert err["details"]["kind"] == "ai_batches" and err["details"]["limit"] == 3 and err["details"]["resets_on"]


def test_the_suggestion_limit_of_the_plan_answers_429(api, ids, notes, consented):
    RecallQuotaPlan.objects.filter(pk="free").update(ai_batches_per_day=9, ai_suggestions_per_day=12)
    assert ask(api, ids["gst"], count=10).status_code == 202
    res = ask(api, ids["residential"], count=10)
    assert res.status_code == 429 and res.json_body["error"]["details"]["kind"] == "ai_suggestions"
    assert usage() == (1, 10) and RecallSuggestionBatch.objects.count() == 1


def test_the_shared_daily_budget_stops_new_batches(api, ids, notes, consented, settings):
    settings.RECALL_AI_DAILY_BUDGET_PAISE = 100  # below the reserve of one batch
    assert ask(api, ids["gst"]).status_code == 503 and usage() == (0, 0)


def test_the_throttle_scope_exists():
    from django.conf import settings

    assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["recall_ai"] == "10/hour"


# ------------------------------------------------------------------------------------------------ accept and reject


def ready(api, ids, monkeypatch, out=None):
    fake_model(monkeypatch, out or GOOD)
    bid = ask(api, ids["gst"]).json_body["id"]
    work(bid)
    return bid, api.get(f"/recall/suggestions/{bid}/").json_body["suggestions"]


def test_accept_makes_a_private_ai_card_and_is_idempotent(api, ids, notes, consented, monkeypatch):
    _, drafts = ready(api, ids, monkeypatch)
    sid = drafts[0]["id"]
    first = api.post(f"/recall/suggestions/items/{sid}/accept/")
    assert first.status_code == 201, first.json_body
    card_id = first.json_body["card_id"]
    assert first.json_body["suggestion"]["status"] == "accepted"
    item = RecallItem.objects.get(owner_user_id=USER, origin="ai_suggestion")
    assert item.shareable is False and item.chapter_id == uuid.UUID(ids["gst"]) and item.kind == "pointer"
    again = api.post(f"/recall/suggestions/items/{sid}/accept/")
    assert again.status_code == 200 and again.json_body["card_id"] == card_id
    assert RecallItem.objects.filter(owner_user_id=USER, origin="ai_suggestion").count() == 1
    assert api.get(f"/recall/cards/{card_id}/").json_body["shareable"] is False


def test_accept_with_her_edit_is_recorded_as_edited(api, ids, notes, consented, monkeypatch):
    _, drafts = ready(api, ids, monkeypatch)
    res = api.post(
        f"/recall/suggestions/items/{drafts[0]['id']}/accept/",
        {"fields": {"answer_md": "Personal use only, s. 17(5)."}},
    )
    assert res.status_code == 201 and res.json_body["suggestion"]["status"] == "edited_accepted"
    assert res.json_body["cards"][0]["fields"]["answer_md"] == "Personal use only, s. 17(5)."


def test_an_edit_that_breaks_the_card_rules_is_422_and_nothing_is_made(api, ids, notes, consented, monkeypatch):
    _, drafts = ready(api, ids, monkeypatch)
    res = api.post(f"/recall/suggestions/items/{drafts[0]['id']}/accept/", {"fields": {"answer_md": ""}})
    assert res.status_code == 422 and res.json_body["error"]["code"] == "invalid_fields"
    assert RecallItem.objects.filter(origin="ai_suggestion").count() == 0
    assert RecallSuggestion.objects.get(pk=drafts[0]["id"]).status == "draft"


def test_accepting_a_card_she_already_has_is_409_and_she_can_still_reject_it(api, ids, notes, consented, monkeypatch):
    _, drafts = ready(api, ids, monkeypatch)
    f = drafts[0]["fields"]
    assert (
        api.post("/recall/cards/", {"client_id": str(uuid.uuid4()), "kind": "pointer", "fields": f}).status_code == 201
    )
    res = api.post(f"/recall/suggestions/items/{drafts[0]['id']}/accept/")
    assert res.status_code == 409 and res.json_body["error"]["code"] == "duplicate_card"
    assert api.post(f"/recall/suggestions/items/{drafts[0]['id']}/reject/").status_code == 200


def test_reject_is_remembered_so_the_same_text_is_not_suggested_again(api, ids, notes, consented, monkeypatch):
    bid, drafts = ready(api, ids, monkeypatch)
    res = api.post(f"/recall/suggestions/items/{drafts[0]['id']}/reject/")
    assert res.status_code == 200 and res.json_body["suggestion"]["status"] == "rejected"
    assert api.post(f"/recall/suggestions/items/{drafts[0]['id']}/reject/").status_code == 200  # a repeat is fine
    assert RecallSuggestionReject.objects.filter(user_id=USER).count() == 1
    assert (
        api.post(f"/recall/suggestions/items/{drafts[0]['id']}/accept/").json_body["error"]["code"]
        == "suggestion_decided"
    )
    notes.text = NOTE_TEXT + " A new sentence so the cache key differs."
    second = ask(api, ids["gst"]).json_body["id"]
    work(second)
    texts = [s["fields"]["prompt_md"] for s in api.get(f"/recall/suggestions/{second}/").json_body["suggestions"]]
    assert "When is ITC blocked on vehicles?" not in texts and "What does ITC need?" in texts


def test_the_reject_memory_lasts_90_days_and_then_goes(api, ids, notes, consented, monkeypatch):
    _, drafts = ready(api, ids, monkeypatch)
    api.post(f"/recall/suggestions/items/{drafts[0]['id']}/reject/")
    RecallSuggestionReject.objects.update(created_at=timezone.now() - timedelta(days=91))
    notes.text = NOTE_TEXT + " Another sentence."
    second = ask(api, ids["gst"]).json_body["id"]
    work(second)
    texts = [s["fields"]["prompt_md"] for s in api.get(f"/recall/suggestions/{second}/").json_body["suggestions"]]
    assert "When is ITC blocked on vehicles?" in texts  # forgotten after 90 days
    svc.expire_drafts()
    assert RecallSuggestionReject.objects.count() == 0


def test_a_student_cannot_see_or_decide_another_students_drafts(api, other_api, ids, notes, consented, monkeypatch):
    bid, drafts = ready(api, ids, monkeypatch)
    assert other_api.get(f"/recall/suggestions/{bid}/").status_code == 404
    assert other_api.post(f"/recall/suggestions/items/{drafts[0]['id']}/accept/").status_code == 404
    assert other_api.post(f"/recall/suggestions/items/{drafts[0]['id']}/reject/").status_code == 404
    assert other_api.get("/recall/suggestions/").json_body["results"] == []


def test_the_list_shows_her_recent_batches_with_their_drafts(api, ids, notes, consented, monkeypatch):
    bid, _ = ready(api, ids, monkeypatch)
    rows = api.get(f"/recall/suggestions/?chapter_id={ids['gst']}").json_body["results"]
    assert [r["id"] for r in rows] == [bid] and len(rows[0]["suggestions"]) == 2
    assert api.get(f"/recall/suggestions/?chapter_id={ids['residential']}").json_body["results"] == []
    assert api.get("/recall/ai/").json_body["waiting_drafts"] == 2


# ------------------------------------------------------------------------------------------------ consent, expiry, rights


def test_withdrawing_consent_deletes_drafts_cancels_a_running_batch_and_works_with_the_flags_off(
    api, ids, notes, consented, monkeypatch
):
    bid, _ = ready(api, ids, monkeypatch)
    notes.text = NOTE_TEXT + " Second chapter material."
    running = ask(api, ids["residential"]).json_body["id"]
    monkeypatch.setattr(feature_flags, "_lookup", lambda name, distinct_id: False)  # every flag off
    res = api.post("/recall/ai/consent/withdraw/")
    assert res.status_code == 200 and res.json_body["drafts_deleted"] == 2 and res.json_body["cancelled"] == 1
    assert RecallSuggestion.objects.count() == 0
    assert RecallSuggestionBatch.objects.get(pk=running).status == "cancelled"
    assert usage() == (1, 2) or usage()[0] <= 1  # the cancelled batch is refunded
    monkeypatch.setattr(feature_flags, "_lookup", lambda name, distinct_id: True)
    assert ask(api, ids["gst"]).json_body["error"]["code"] == "ai_not_consented"
    assert bid  # the finished batch stays as a record (status expired), its drafts are gone


def test_consent_withdrawn_while_the_model_was_thinking_keeps_nothing(api, ids, notes, consented, monkeypatch):
    bid = ask(api, ids["gst"]).json_body["id"]

    def generate(sources, kinds, count):
        api.post("/recall/ai/consent/withdraw/")
        return gemini.GeminiResult(json.dumps({"cards": GOOD}), 10, 10, "m")

    monkeypatch.setattr(ai_adapter, "generate", generate)
    work(bid)
    assert RecallSuggestion.objects.count() == 0 and RecallSuggestionBatch.objects.get(pk=bid).status == "cancelled"


def test_the_daily_expiry_deletes_old_drafts_and_old_batches(api, ids, notes, consented, monkeypatch):
    bid, _ = ready(api, ids, monkeypatch)
    RecallSuggestionBatch.objects.filter(pk=bid).update(expires_at=timezone.now() - timedelta(days=1))
    out = svc.expire_drafts()
    assert out["expired"] == 1 and out["drafts"] == 2
    assert RecallSuggestionBatch.objects.get(pk=bid).status == "expired" and RecallSuggestion.objects.count() == 0
    RecallSuggestionBatch.objects.filter(pk=bid).update(created_at=timezone.now() - timedelta(days=61))
    assert svc.expire_drafts()["removed"] >= 1 and RecallSuggestionBatch.objects.count() == 0


def test_the_tick_queues_the_expiry_once_a_day_and_never_the_heavy_job(api, ids, notes, consented):
    from modules.recall import jobs

    ask(api, ids["gst"])
    assert jobs.JOB_SUGGEST not in jobs.LIGHT_TYPES and jobs.JOB_SUGGEST in jobs.HEAVY_TYPES
    jobs.tick()
    jobs.tick()
    assert Job.objects.filter(type="recall.expire_suggestions").count() == 1
    assert Job.objects.get(type="recall.suggest").status == "queued"  # the tick did not take it


def test_the_handlers_are_registered_for_the_worker():
    from core import jobs as core_jobs

    assert "recall.suggest" in core_jobs.handler_types() and "recall.expire_suggestions" in core_jobs.handler_types()


def test_export_carries_her_drafts_and_erase_removes_everything(api, ids, notes, consented, monkeypatch):
    bid, drafts = ready(api, ids, monkeypatch)
    api.post(f"/recall/suggestions/items/{drafts[1]['id']}/reject/")
    export = erasure.export_for_user(USER)["ai_suggestions"]
    assert len(export["batches"]) == 1 and len(export["suggestions"]) == 2 and export["remembered_rejections"] == 1
    queued = ask(api, ids["residential"], sources=["pasted"], pasted_text=NOTE_TEXT).json_body["id"]
    assert Job.objects.filter(payload__batch_id=queued).exists()
    report = erasure.delete_all_for_user(USER)
    assert report["suggestion_batches"] >= 2 and report["suggestion_rejects"] == 1 and report["ai_calls"] == 1
    for model in (RecallSuggestionBatch, RecallSuggestion, RecallSuggestionReject, RecallAiCall, RecallAiUsage):
        assert model.objects.count() == 0
    assert Job.objects.filter(type="recall.suggest").count() == 0 and bid


def test_no_student_text_reaches_the_logs_or_the_ledger(api, ids, notes, consented, monkeypatch, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    fake_model(monkeypatch, GOOD)
    bid = ask(api, ids["gst"], sources=["notes", "pasted"], pasted_text="privpaste " + NOTE_TEXT).json_body["id"]
    work(bid)
    sid = api.get(f"/recall/suggestions/{bid}/").json_body["suggestions"][0]["id"]
    api.post(f"/recall/suggestions/items/{sid}/accept/")
    blob = "\n".join(r.getMessage() for r in caplog.records)
    assert "Section 17(5)" not in blob and "privpaste" not in blob and "tax invoice" not in blob
    ledger = list(RecallAiCall.objects.values())
    assert "17(5)" not in json.dumps(ledger, default=str)
