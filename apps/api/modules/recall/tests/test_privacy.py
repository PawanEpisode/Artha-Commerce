"""
Privacy checks for recall (PRD 8.4, ERD 8): card text, note text, deck titles and ids never reach the logs or Sentry.

* log capture: a create, review, edit, export and erase flow with every log level on, then a search of every record;
* Sentry: the real SDK with a capturing transport, failing recall requests that carry card text in the body, the query string and
  the local variables, then a search of every envelope. The unit tests of the scrubbing rules live in `core/tests/test_sentry.py`.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

import pytest
import sentry_sdk
from django.test import Client
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.transport import Transport

from core.sentry import before_send, before_send_transaction
from modules.recall.services import cards as card_services

from .support import made, new

pytestmark = pytest.mark.django_db

TEXT = f"privtext-{uuid.uuid4().hex}"  # a distinctive string no log line or event should ever hold
NOTE = f"privnote-{uuid.uuid4().hex}"
SELECTION = f"privselect-{uuid.uuid4().hex}"


def _text_of(record: logging.LogRecord) -> str:
    """Everything a handler could write for a record: the message, the traceback and every attribute (extras included)."""
    return logging.Formatter("%(name)s %(levelname)s %(message)s").format(record) + " " + repr(vars(record))


# ------------------------------------------------------------------------------------------------------ log capture
def test_a_whole_study_flow_writes_no_card_text_note_text_or_card_ids_to_the_logs(api, capsys, caplog):
    caplog.set_level(logging.DEBUG)
    card = made(api, {"prompt_md": f"{TEXT} question?", "answer_md": f"{TEXT} answer"}, tags=[TEXT[:20]])
    other = made(api, {"prompt_md": f"{TEXT} second?", "answer_md": f"{TEXT} again"})
    now = datetime.now(UTC).isoformat()
    ev = {"id": str(uuid.uuid4()), "card_id": card["id"], "rating": 3, "reviewed_at": now, "device_id": "dev-1"}
    assert api.post("/recall/reviews/", ev).status_code == 201
    batch = {"events": [{**ev, "id": str(uuid.uuid4()), "card_id": other["id"]}]}
    assert api.post("/recall/reviews/batch/", batch).status_code == 200
    current = api.get(f"/recall/cards/{card['id']}/").json_body
    edit = {"base_rev": current["rev"], "fields": {"answer_md": f"{TEXT} edited"}}
    assert api.patch(f"/recall/cards/{card['id']}/", edit).status_code == 200
    stale = api.patch(f"/recall/cards/{card['id']}/", {"base_rev": 1, "fields": {"answer_md": f"{TEXT} stale"}})
    assert stale.status_code == 409  # a refused write logs a warning, which must not hold the text either
    refused = new(api, {"prompt_md": f"{TEXT} bad", "answer_md": "x" * 5000})
    assert refused.status_code == 422
    selection = {
        "client_id": str(uuid.uuid4()),
        "origin": "note_highlight",
        "selection_text": f"{SELECTION} selected passage",
        "source": {"module": "notes", "object_id": "doc-1", "locator": {"page": 1}},
    }
    api.post("/recall/cards/from-selection/", selection)
    assert api.get(f"/recall/cards/?q={TEXT}").status_code == 200
    assert api.get("/recall/queue/").status_code == 200
    assert api.get("/recall/pack/").status_code == 200
    assert api.get("/recall/export/").status_code == 200
    csv = api.c.get("/api/v1/recall/export/cards.csv")
    assert csv.status_code == 200 and b"".join(csv.streaming_content)
    assert api.post("/recall/erase/", {"confirm": "ERASE"}).status_code == 200

    out, err = capsys.readouterr()
    haystacks = [_text_of(r) for r in caplog.records] + [out, err]
    assert caplog.records  # the capture works: the requests above do log something
    secrets = [TEXT, NOTE, SELECTION, card["id"], other["id"], card["item_id"], card["item_version_id"]]
    leaks = [(s[:14], i) for i, h in enumerate(haystacks) for s in secrets if s in h]
    assert leaks == []


def test_a_failing_write_logs_no_card_text(api, monkeypatch, caplog):
    """An unexpected error becomes one 500 log record with a traceback: the traceback shows code, never the request body."""
    caplog.set_level(logging.DEBUG)

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(card_services, "create_card", boom)
    client = Client(raise_request_exception=False, HTTP_AUTHORIZATION=api.c.defaults["HTTP_AUTHORIZATION"])
    body = {"client_id": str(uuid.uuid4()), "kind": "pointer", "fields": {"prompt_md": TEXT, "answer_md": TEXT}}
    res = client.post("/api/v1/recall/cards/", data=json.dumps(body), content_type="application/json")
    assert res.status_code == 500
    assert any(r.levelno >= logging.ERROR for r in caplog.records)
    assert [r for r in caplog.records if TEXT in _text_of(r)] == []


# ------------------------------------------------------------------------------------------------------ Sentry
class Capture(Transport):
    sent: list = []

    def capture_envelope(self, envelope):
        Capture.sent.append(envelope)


@pytest.fixture
def sentry_capture():
    Capture.sent = []
    sentry_sdk.init(
        dsn="https://public@example.ingest.sentry.io/1",
        transport=Capture,
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        send_default_pii=False,
        before_send=before_send,
        before_send_transaction=before_send_transaction,
    )
    yield Capture.sent
    sentry_sdk.get_client().close()
    sentry_sdk.init()  # no DSN: the SDK is off again for the other tests


def _payloads(envelopes) -> list[dict]:
    out = []
    for envelope in envelopes:
        out.append(envelope.headers)
        out += [item.payload.json for item in envelope.items if item.payload.json]
    return out


@pytest.mark.parametrize("case", ["create", "edit", "search", "review", "batch", "selection"])
def test_a_failing_recall_request_never_sends_card_text_or_ids_to_sentry(api, monkeypatch, sentry_capture, case):
    card = made(api, {"prompt_md": f"{TEXT} stored", "answer_md": "A"})
    when = datetime.now(UTC).isoformat()
    event = {"id": str(uuid.uuid4()), "card_id": card["id"], "rating": 3, "reviewed_at": when, "device_id": "dev-1"}
    requests = {
        "create": (
            "post",
            "/api/v1/recall/cards/",
            {"client_id": str(uuid.uuid4()), "kind": "pointer", "fields": {"prompt_md": TEXT, "answer_md": TEXT}},
        ),
        "edit": ("patch", f"/api/v1/recall/cards/{card['id']}/", {"base_rev": 1, "fields": {"answer_md": TEXT}}),
        "search": ("get", f"/api/v1/recall/cards/?q={TEXT}", None),
        "review": ("post", "/api/v1/recall/reviews/", event),
        "batch": ("post", "/api/v1/recall/reviews/batch/", {"events": [event]}),
        "selection": (
            "post",
            "/api/v1/recall/cards/from-selection/",
            {
                "client_id": str(uuid.uuid4()),
                "origin": "note_highlight",
                "selection_text": SELECTION,
                "source": {"module": "notes", "object_id": "d", "locator": {}},
            },
        ),
    }
    method, url, body = requests[case]

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    from modules.recall import selectors, services

    for owner, name in (
        (card_services, "create_card"),
        (card_services, "update_card"),
        (card_services, "create_card_from_selection"),
        (selectors, "list_cards"),
        (services.reviews, "submit_review"),
        (services.reviews, "submit_reviews"),
    ):
        monkeypatch.setattr(owner, name, boom)
    client = Client(raise_request_exception=False, HTTP_AUTHORIZATION=api.c.defaults["HTTP_AUTHORIZATION"])
    kwargs = {"data": json.dumps(body), "content_type": "application/json"} if body is not None else {}
    assert getattr(client, method)(url, **kwargs).status_code == 500
    sentry_sdk.flush()

    payloads = _payloads(sentry_capture)
    assert any("exception" in p for p in payloads), "the SDK sent no error event, so this test would pass for nothing"
    dump = json.dumps(payloads, default=str)
    leaks = [
        name
        for name, s in (("text", TEXT), ("selection", SELECTION), ("card id", card["id"]), ("item id", card["item_id"]))
        if s in dump
    ]
    context = {
        n: [dump[max(0, dump.find(x) - 150) : dump.find(x) + 80] for x in (TEXT, card["id"]) if x in dump]
        for n in leaks
    }
    assert leaks == [], context
    assert all(
        "data" not in (p.get("request") or {}) and "query_string" not in (p.get("request") or {}) for p in payloads
    )


# ------------------------------------------------------------------------------------------------------ R2-W1: exam routes
def _exam_world(scheme, monkeypatch):
    """An enrolment 30 days out and a few weak mandatory cards whose text is the marker; the clock is frozen."""
    from datetime import timedelta

    from django.utils import timezone

    from modules.coverage.models import Enrollment
    from modules.recall.models import RecallItem

    from .factories import make_card, make_item
    from .w5 import ME

    now = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)
    monkeypatch.setattr(timezone, "now", lambda: now)
    Enrollment.objects.create(
        user_id=ME, scheme=scheme, level=scheme.level, exam_date=(now + timedelta(days=30)).date()
    )
    cards = []
    for i in range(3):
        item = make_item(ME, text=f"{TEXT} exam {i}")
        RecallItem.objects.filter(pk=item.pk).update(scheme_id=scheme.id)
        last = now - timedelta(days=30)
        cards.append(
            make_card(
                item, ME, importance=2, state=2, stability=3.0, difficulty=5.0, reps=3, last_review_at=last,
                due_scheduled_at=last + timedelta(days=3), due_at=last + timedelta(days=3),
            )
        )  # fmt: skip
    return cards


def test_the_exam_screens_jobs_and_cram_write_no_card_text_or_ids_to_the_logs(api, scheme, capsys, caplog, monkeypatch):
    from modules.recall import jobs
    from modules.recall.services import exam as exam_service

    from .w5 import ME

    caplog.set_level(logging.DEBUG)
    cards = _exam_world(scheme, monkeypatch)
    assert api.get("/recall/quick-revision/plan/?minutes=20").status_code == 200
    assert api.get("/recall/queue/?source=quick").status_code == 200
    assert api.get("/recall/today/").status_code == 200
    assert api.get("/recall/pack/").status_code == 200
    assert (
        api.get("/recall/queue/?source=cram").status_code == 422
    )  # not open yet: a refusal logs nothing personal either
    exam_service.reevaluate_student(ME)
    jobs.tick()

    out, err = capsys.readouterr()
    haystacks = [_text_of(r) for r in caplog.records] + [out, err]
    assert caplog.records
    secrets = [TEXT] + [str(c.id) for c in cards] + [str(c.item_id) for c in cards]
    assert [(s[:14], i) for i, h in enumerate(haystacks) for s in secrets if s in h] == []


def test_a_failing_quick_plan_sends_no_card_text_or_ids_to_sentry(api, scheme, monkeypatch, sentry_capture):
    cards = _exam_world(scheme, monkeypatch)
    from modules.recall import selectors

    def boom(*args, **kwargs):
        raise RuntimeError("unexpected")

    monkeypatch.setattr(selectors, "quick_plan", boom)
    client = Client(raise_request_exception=False, HTTP_AUTHORIZATION=api.c.defaults["HTTP_AUTHORIZATION"])
    assert client.get("/api/v1/recall/quick-revision/plan/?minutes=20").status_code == 500
    sentry_sdk.flush()
    payloads = _payloads(sentry_capture)
    assert any("exception" in p for p in payloads)
    dump = json.dumps(payloads, default=str)
    assert TEXT not in dump and all(str(c.id) not in dump for c in cards)
    assert all("query_string" not in (p.get("request") or {}) for p in payloads)
