"""
Results notifications end to end (PRD X-01.2 FR-A15..FR-A18, ERD X-01.2):
- Background results notifications in `results` category, priority 2
- Success and failure copy and deep links for:
    * `notes_ocr_done` -> /app/notes/pdf/{doc_id}
    * `notes_export_ready` -> /app/notes/pdf/{doc_id}
    * `notes_summary_ready` -> /app/notes
    * `recall_suggestions_ready` -> /app/recall/suggestions
- Deduplication by job_id / batch_id
- Flag gating: away_alerts flag off suppresses push
- Ops kill switch: NOTIFICATIONS_DISABLED_EVENTS suppresses push
- Privacy: no user content in payloads
- Transaction on_commit rollback safety
"""

import json
import uuid

import pytest
from django.db import transaction

from modules.notifications.domain.catalogue import Category
from modules.notifications.domain.enums import DeliveryStatus, SuppressReason
from modules.notifications.models import Delivery, Notification
from modules.notifications.services.notify import notify
from modules.notifications.tests.helpers import register
from modules.notifications.tests.tracker_bench import USER

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def away_alerts_on(monkeypatch):
    """Enable all notification flags including away_alerts."""
    monkeypatch.setattr("modules.notifications.flags.flag_enabled", lambda *a, **k: True)


@pytest.fixture(autouse=True)
def android():
    return register(USER, platform="android", browser="chrome").device


def sent_payloads(fake_push) -> list[dict]:
    return [json.loads(message.body) for _, message in fake_push.sent]


def test_notes_ocr_done_success(android, fake_push):
    result = notify(
        USER,
        "notes_ocr_done",
        context={"doc_id": "doc-123", "job_id": "ocr-job-1", "failed": False},
        dedupe_ref={"job_id": "ocr-job-1"},
    )
    assert result.created is True
    notif = result.notification
    assert notif.category == Category.RESULTS
    assert notif.priority == 2
    assert notif.dedupe_key == "notes_ocr:ocr-job-1"
    assert notif.title == "OCR finished"
    assert notif.body == "Your scanned pages are searchable now."
    assert notif.deep_link == "/app/notes/pdf/doc-123"

    payloads = sent_payloads(fake_push)
    assert len(payloads) == 1
    assert payloads[0]["title"] == "OCR finished"
    assert payloads[0]["url"] == f"/app/notes/pdf/doc-123?n={notif.id}"
    assert payloads[0]["tag"] == "notes_ocr:ocr-job-1"


def test_notes_ocr_done_failure(android, fake_push):
    result = notify(
        USER,
        "notes_ocr_done",
        context={"doc_id": "doc-123", "job_id": "ocr-job-fail", "failed": True},
        dedupe_ref={"job_id": "ocr-job-fail"},
    )
    notif = result.notification
    assert notif.title == "OCR could not finish"
    assert notif.body == "Your file is safe. Try again."
    assert notif.deep_link == "/app/notes/pdf/doc-123"

    payloads = sent_payloads(fake_push)
    assert len(payloads) == 1
    assert payloads[0]["title"] == "OCR could not finish"


def test_notes_export_ready_success_and_failure(android, fake_push):
    # Success
    res1 = notify(
        USER,
        "notes_export_ready",
        context={"doc_id": "doc-456", "job_id": "exp-1", "failed": False},
        dedupe_ref={"job_id": "exp-1"},
    )
    notif1 = res1.notification
    assert notif1.category == Category.RESULTS
    assert notif1.priority == 2
    assert notif1.dedupe_key == "notes_export:exp-1"
    assert notif1.title == "Your PDF export is ready"
    assert notif1.body == "Download it from the reader."
    assert notif1.deep_link == "/app/notes/pdf/doc-456"

    # Failure
    res2 = notify(
        USER,
        "notes_export_ready",
        context={"doc_id": "doc-456", "job_id": "exp-2", "failed": True},
        dedupe_ref={"job_id": "exp-2"},
    )
    notif2 = res2.notification
    assert notif2.title == "Export could not finish"
    assert notif2.body == "Try exporting again from the reader."
    assert notif2.deep_link == "/app/notes/pdf/doc-456"

    assert len(fake_push.sent) == 2


def test_notes_summary_ready_success_and_failure(android, fake_push):
    # Success
    res1 = notify(
        USER,
        "notes_summary_ready",
        context={"job_id": "sum-1", "failed": False},
        dedupe_ref={"job_id": "sum-1"},
    )
    notif1 = res1.notification
    assert notif1.category == Category.RESULTS
    assert notif1.priority == 2
    assert notif1.dedupe_key == "notes_summary:sum-1"
    assert notif1.title == "Exam summary ready"
    assert notif1.body == "Open it to review and edit."
    assert notif1.deep_link == "/app/notes"

    # Failure
    res2 = notify(
        USER,
        "notes_summary_ready",
        context={"job_id": "sum-2", "failed": True},
        dedupe_ref={"job_id": "sum-2"},
    )
    notif2 = res2.notification
    assert notif2.title == "Summary could not finish"
    assert notif2.body == "Try again from your chapter notes."
    assert notif2.deep_link == "/app/notes"


def test_recall_suggestions_ready_success_and_failure(android, fake_push):
    # Success
    res1 = notify(
        USER,
        "recall_suggestions_ready",
        context={"batch_id": "batch-1", "failed": False},
        dedupe_ref={"batch_id": "batch-1"},
    )
    notif1 = res1.notification
    assert notif1.category == Category.RESULTS
    assert notif1.priority == 2
    assert notif1.dedupe_key == "recall_suggest:batch-1"
    assert notif1.title == "Card suggestions ready"
    assert notif1.body == "Review them; nothing is added until you accept."
    assert notif1.deep_link == "/app/recall/suggestions"

    # Failure
    res2 = notify(
        USER,
        "recall_suggestions_ready",
        context={"batch_id": "batch-2", "failed": True},
        dedupe_ref={"batch_id": "batch-2"},
    )
    notif2 = res2.notification
    assert notif2.title == "Suggestions could not finish"
    assert notif2.body == "Try generating card suggestions again."
    assert notif2.deep_link == "/app/recall/suggestions"


def test_deduplication_fires_once(android, fake_push):
    r1 = notify(
        USER,
        "notes_ocr_done",
        context={"doc_id": "doc-1", "job_id": "job-dedupe", "failed": False},
        dedupe_ref={"job_id": "job-dedupe"},
    )
    assert r1.created is True
    assert len(fake_push.sent) == 1

    # Second call with same dedupe_ref
    r2 = notify(
        USER,
        "notes_ocr_done",
        context={"doc_id": "doc-1", "job_id": "job-dedupe", "failed": False},
        dedupe_ref={"job_id": "job-dedupe"},
    )
    assert r2.created is False
    assert r2.notification.id == r1.notification.id
    # No duplicate push sent
    assert len(fake_push.sent) == 1


def test_away_alerts_flag_off_suppresses_push(android, fake_push, monkeypatch):
    monkeypatch.setattr(
        "modules.notifications.flags.flag_enabled",
        lambda name, *a, **k: False if name == "away_alerts" else True,
    )
    res = notify(
        USER,
        "notes_ocr_done",
        context={"doc_id": "doc-1", "job_id": "job-flag-off", "failed": False},
        dedupe_ref={"job_id": "job-flag-off"},
    )
    assert res.created is True
    # Inbox row exists
    assert Notification.objects.filter(pk=res.notification.id).exists()
    # Push is suppressed
    assert len(fake_push.sent) == 0
    delivery = Delivery.objects.get(notification=res.notification)
    assert delivery.status == DeliveryStatus.SUPPRESSED
    assert delivery.suppress_reason == SuppressReason.FLAG_OFF


def test_disabled_events_setting_suppresses_push(android, fake_push, settings):
    settings.NOTIFICATIONS_DISABLED_EVENTS = ("notes_ocr_done",)
    res = notify(
        USER,
        "notes_ocr_done",
        context={"doc_id": "doc-1", "job_id": "job-disabled-event", "failed": False},
        dedupe_ref={"job_id": "job-disabled-event"},
    )
    assert res.created is True
    assert len(fake_push.sent) == 0
    delivery = Delivery.objects.get(notification=res.notification)
    assert delivery.status == DeliveryStatus.SUPPRESSED
    assert delivery.suppress_reason == SuppressReason.FLAG_OFF


def test_privacy_no_user_content_in_payloads(android, fake_push, monkeypatch):
    monkeypatch.setattr("modules.notifications.domain.policy.DAILY_CAP", 10)
    events_data = [
        ("notes_ocr_done", {"doc_id": "d1", "job_id": "j1", "failed": False}, {"job_id": "j1"}),
        ("notes_export_ready", {"doc_id": "d2", "job_id": "j2", "failed": False}, {"job_id": "j2"}),
        ("notes_summary_ready", {"job_id": "j3", "failed": False}, {"job_id": "j3"}),
        ("recall_suggestions_ready", {"batch_id": "b1", "failed": False}, {"batch_id": "b1"}),
    ]
    for key, ctx, ref in events_data:
        notify(USER, key, context=ctx, dedupe_ref=ref)

    assert len(fake_push.sent) == 4
    for _, message in fake_push.sent:
        payload = json.loads(message.body)
        assert set(payload.keys()) <= {"v", "id", "category", "title", "body", "tag", "url", "actions"}
        # Ensure no user text or secrets leaked into title or body
        assert not any(sensitive in payload["title"].lower() for sensitive in ["token", "secret", "password"])
        assert not any(sensitive in payload["body"].lower() for sensitive in ["token", "secret", "password"])


def test_on_commit_rollback_sends_nothing(android, fake_push, django_capture_on_commit_callbacks):
    try:
        with transaction.atomic():

            def _send():
                notify(
                    USER,
                    "notes_ocr_done",
                    context={"doc_id": "doc-rb", "job_id": "job-rb", "failed": False},
                    dedupe_ref={"job_id": "job-rb"},
                )

            transaction.on_commit(_send)
            # Intentionally fail the transaction
            raise ValueError("simulated rollback")
    except ValueError:
        pass

    assert Notification.objects.filter(dedupe_key="notes_ocr:job-rb").count() == 0
    assert len(fake_push.sent) == 0


def test_service_ocr_helpers(android, fake_push, django_capture_on_commit_callbacks):
    from modules.notes.services import ocr

    with django_capture_on_commit_callbacks(execute=True):
        ocr._notify_ocr_done(USER, "doc-ocr-1", "j-ocr-1")
    assert Notification.objects.filter(dedupe_key="notes_ocr:j-ocr-1").count() == 1
    assert len(fake_push.sent) == 1

    with django_capture_on_commit_callbacks(execute=True):
        ocr._notify_ocr_failed(USER, "doc-ocr-1", "j-ocr-2")
    assert Notification.objects.filter(dedupe_key="notes_ocr:j-ocr-2").count() == 1
    assert len(fake_push.sent) == 2


def test_service_export_helpers(android, fake_push, django_capture_on_commit_callbacks):
    from types import SimpleNamespace

    from modules.notes.services import exports

    job_done = SimpleNamespace(user_id=USER, id=uuid.uuid4(), document_id="doc-exp-1")
    with django_capture_on_commit_callbacks(execute=True):
        exports._notify_export_done(job_done, "doc-exp-1")
    assert Notification.objects.filter(dedupe_key=f"notes_export:{job_done.id}").count() == 1

    job_fail = SimpleNamespace(user_id=USER, id=uuid.uuid4(), document_id="doc-exp-1")
    with django_capture_on_commit_callbacks(execute=True):
        exports._notify_export_failed(job_fail)
    assert Notification.objects.filter(dedupe_key=f"notes_export:{job_fail.id}").count() == 1


def test_service_summary_helpers(android, fake_push, django_capture_on_commit_callbacks):
    from types import SimpleNamespace

    from modules.notes.services import summary

    job_ready = SimpleNamespace(user_id=USER, id=uuid.uuid4())
    with django_capture_on_commit_callbacks(execute=True):
        summary._notify_summary_ready(job_ready)
    assert Notification.objects.filter(dedupe_key=f"notes_summary:{job_ready.id}").count() == 1

    job_fail = SimpleNamespace(user_id=USER, id=uuid.uuid4())
    with django_capture_on_commit_callbacks(execute=True):
        summary._notify_summary_failed(job_fail)
    assert Notification.objects.filter(dedupe_key=f"notes_summary:{job_fail.id}").count() == 1


def test_service_suggestions_helpers(android, fake_push, django_capture_on_commit_callbacks):
    from types import SimpleNamespace

    from modules.recall.services import suggestions

    batch_ready = SimpleNamespace(user_id=USER, id=uuid.uuid4())
    with django_capture_on_commit_callbacks(execute=True):
        suggestions._notify_suggestions_ready(batch_ready)
    assert Notification.objects.filter(dedupe_key=f"recall_suggest:{batch_ready.id}").count() == 1

    batch_fail = SimpleNamespace(user_id=USER, id=uuid.uuid4())
    with django_capture_on_commit_callbacks(execute=True):
        suggestions._notify_suggestions_failed(batch_fail)
    assert Notification.objects.filter(dedupe_key=f"recall_suggest:{batch_fail.id}").count() == 1
