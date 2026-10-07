"""Document quota primitives: reserve and release bytes with a slot, monthly charges and refunds, the plan accessors."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from modules.notes.domain import quota as domain
from modules.notes.errors import QuotaExceeded
from modules.notes.models import MonthlyUsage, QuotaPlan, QuotaUsage
from modules.notes.services import quota

pytestmark = pytest.mark.django_db

USER = uuid.UUID("3f2b8c7e-6d2e-4f0e-9a45-0f9e5b3e1c11")
MB = 1024 * 1024
LIMITS = domain.FREE  # 500 MB, 100 documents, 300 OCR pages, 10 exports


def usage():
    return QuotaUsage.objects.get(pk=USER)


def test_the_pure_rule_names_the_limit_that_would_break():
    assert domain.document_limit_hit(0, 0, 50 * MB, LIMITS) is None
    assert domain.document_limit_hit(450 * MB, 0, 50 * MB, LIMITS) is None  # exactly full still fits
    assert domain.document_limit_hit(450 * MB + 1, 0, 50 * MB, LIMITS) == "storage"
    assert (
        domain.document_limit_hit(0, 99, 1, LIMITS) is None
        and domain.document_limit_hit(0, 100, 1, LIMITS) == "documents"
    )
    assert (
        domain.document_limit_hit(500 * MB, 100, 1, LIMITS) == "storage"
    )  # both: the clean-up that helps most comes first


def test_reserving_takes_the_bytes_and_one_slot_and_releasing_gives_both_back():
    quota.reserve_document(USER, 40 * MB)
    quota.reserve_document(USER, 10 * MB)
    assert (usage().bytes_used, usage().docs_active) == (50 * MB, 2)
    quota.release_document(USER, 40 * MB)
    assert (usage().bytes_used, usage().docs_active) == (10 * MB, 1)
    quota.release_document(USER, 999 * MB)  # clamps at zero, never negative
    quota.release_document(USER, 1)
    assert (usage().bytes_used, usage().docs_active) == (0, 0)
    quota.release_document(uuid.uuid4(), 5)  # a student whose usage row is gone is tolerated


def test_storage_that_does_not_fit_is_refused_with_the_agreed_details_and_changes_nothing():
    quota.ensure_usage(USER)
    QuotaUsage.objects.filter(pk=USER).update(bytes_used=430 * MB, docs_active=5)
    quota.reserve_document(USER, 70 * MB)  # 500 MB exactly
    with pytest.raises(QuotaExceeded) as caught:
        quota.reserve_document(USER, 1)
    assert caught.value.extra == {"kind": "storage", "used": 500 * MB, "limit": 500 * MB, "plan": "free"}
    assert (usage().bytes_used, usage().docs_active) == (500 * MB, 6)


def test_a_full_library_is_refused_as_documents_even_for_a_tiny_file():
    quota.ensure_usage(USER)
    QuotaUsage.objects.filter(pk=USER).update(docs_active=100)
    with pytest.raises(QuotaExceeded) as caught:
        quota.reserve_document(USER, 10)
    assert caught.value.extra == {"kind": "documents", "used": 100, "limit": 100, "plan": "free"}
    assert usage().bytes_used == 0


def test_a_plan_row_changes_the_limits():
    QuotaPlan.objects.filter(pk="free").update(max_documents=1)
    quota.reserve_document(USER, 1)
    with pytest.raises(QuotaExceeded):
        quota.reserve_document(USER, 1)
    assert quota.max_documents(USER) == 1


def test_plan_accessors_return_the_plan_values():
    assert quota.max_pages(USER) == 1000 and quota.max_documents(USER) == 100
    assert quota.max_marks_per_document(USER) == 20_000
    assert quota.ocr_pages_per_month(USER) == 300 and quota.exports_per_month(USER) == 10


def test_monthly_charges_stop_at_the_limit_and_refunds_clamp_at_zero():
    quota.charge_monthly(USER, "ocr_pages", 250)
    quota.charge_monthly(USER, "ocr_pages", 50)  # exactly 300
    with pytest.raises(QuotaExceeded) as caught:
        quota.charge_monthly(USER, "ocr_pages", 1)
    assert caught.value.extra == {"kind": "ocr_pages", "used": 300, "limit": 300, "plan": "free"}
    quota.refund_monthly(USER, "ocr_pages", 100)
    assert MonthlyUsage.objects.get(user_id=USER).ocr_pages == 200
    quota.refund_monthly(USER, "ocr_pages", 10_000)
    assert MonthlyUsage.objects.get(user_id=USER).ocr_pages == 0


def test_a_charge_bigger_than_the_limit_is_refused_whole():
    with pytest.raises(QuotaExceeded):
        quota.charge_monthly(USER, "exports", 11)
    assert MonthlyUsage.objects.get(user_id=USER).exports == 0


def test_the_month_is_the_indian_month_and_an_explicit_limit_overrides_the_plan():
    just_before = datetime(2026, 10, 31, 18, 29, tzinfo=UTC)  # 23:59 IST on 31 October
    just_after = just_before + timedelta(minutes=1)  # 00:00 IST on 1 November
    quota.charge_monthly(USER, "exports", 10, now=just_before)
    with pytest.raises(QuotaExceeded):
        quota.charge_monthly(USER, "exports", 1, now=just_before)
    quota.charge_monthly(USER, "exports", 1, now=just_after)  # a new month, a fresh counter
    months = {str(m.month): m.exports for m in MonthlyUsage.objects.filter(user_id=USER)}
    assert months == {"2026-10-01": 10, "2026-11-01": 1}
    quota.charge_monthly(USER, "uploads", 5)  # no plan limit: counted
    with pytest.raises(QuotaExceeded):
        quota.charge_monthly(USER, "uploads", 1, limit=5)  # an explicit limit applies
    quota.charge_monthly(USER, "uploads", 1, limit=6)


def test_reconcile_recomputes_document_slots_and_bytes_from_the_rows():
    from modules.notes import jobs

    from .factories import make_document

    make_document(USER, bytes=1000)  # ready
    make_document(USER, bytes=500, status="reserved")  # holds a slot until it completes or expires
    make_document(USER, bytes=700, status="rejected")  # gave its slot back
    make_document(USER, bytes=300, status="expired")
    quota.ensure_usage(USER)
    QuotaUsage.objects.filter(pk=USER).update(docs_active=9, bytes_used=9)
    out = jobs.reconcile_usage_job({})
    assert out["drifted"] == 1
    row = usage()
    assert row.docs_active == 2  # ready and reserved
    assert row.bytes_used == 4 * 1000  # the sum of the four attachments' own bytes (the factory's default)
