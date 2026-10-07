"""
Quota as database facts (ERD decision 10, audit AUD-001/002): every reservation is ONE conditional UPDATE,

    UPDATE notes_quotausage SET notes_active = notes_active + 1 WHERE user_id = :u AND notes_active <= :limit - 1

and zero rows updated means the quota is full. Two concurrent requests for the last slot cannot both pass, because the
database serialises the updates on the row. Never read-then-write. Releases clamp at zero.
"""

from __future__ import annotations

from datetime import datetime

from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from ..domain.quota import FREE, Limits, document_limit_hit, month_start
from ..errors import QuotaExceeded
from ..models import MonthlyUsage, QuotaPlan, QuotaUsage

# monthly counter -> the plan column that limits it (None: counted, not limited)
MONTHLY_LIMITS = {
    "ocr_pages": "ocr_pages_per_month",
    "ai_ocr_pages": "ai_ocr_pages_per_month",
    "ai_summaries": "ai_summaries_per_month",
    "exports": "exports_per_month",
    "uploads": None,
}


def plan_code_for(user_id) -> str:
    """Billing stub: every student is on `free` until a billing module exists."""
    return "free"


def limits_for(user_id) -> Limits:
    row = QuotaPlan.objects.filter(pk=plan_code_for(user_id)).first()
    if row is None:  # a missing row must never mean "unlimited"
        return FREE
    return Limits(**{name: getattr(row, name) for name in Limits.names()})


def ensure_usage(user_id) -> None:
    QuotaUsage.objects.bulk_create([QuotaUsage(user_id=user_id)], ignore_conflicts=True)


def _exceeded(user_id, kind: str, used: int, limit: int) -> QuotaExceeded:
    return QuotaExceeded(extra={"kind": kind, "used": used, "limit": limit, "plan": plan_code_for(user_id)})


def _reserve(user_id, field: str, amount: int, limit: int, kind: str) -> None:
    ensure_usage(user_id)
    updated = QuotaUsage.objects.filter(**{"user_id": user_id, f"{field}__lte": limit - amount}).update(
        **{field: F(field) + amount, "updated_at": timezone.now()}
    )
    if not updated:
        used = QuotaUsage.objects.filter(pk=user_id).values_list(field, flat=True).first() or 0
        raise _exceeded(user_id, kind, used, limit)


def _release(user_id, field: str, amount: int) -> None:
    QuotaUsage.objects.filter(pk=user_id).update(
        **{field: Greatest(F(field) - amount, Value(0)), "updated_at": timezone.now()}
    )


def reserve_note(user_id) -> None:
    _reserve(user_id, "notes_active", 1, limits_for(user_id).max_notes, "notes")


def release_note(user_id) -> None:
    _release(user_id, "notes_active", 1)


def reserve_tag(user_id) -> None:
    _reserve(user_id, "tags_count", 1, limits_for(user_id).max_tags, "tags")


def release_tag(user_id, amount: int = 1) -> None:
    _release(user_id, "tags_count", amount)


def reserve_bytes(user_id, amount: int) -> None:
    """Storage (images now, PDFs in R2): the media kinds call this when an upload is reserved."""
    _reserve(user_id, "bytes_used", amount, limits_for(user_id).storage_bytes, "storage")


def release_bytes(user_id, amount: int) -> None:
    _release(user_id, "bytes_used", amount)


def reserve_document(user_id, amount: int) -> None:
    """
    A PDF takes bytes AND a document slot in ONE statement (ERD 2.11):

        UPDATE notes_quotausage SET bytes_used = bytes_used + :b, docs_active = docs_active + 1
        WHERE user_id = :u AND bytes_used + :b <= :limit_bytes AND docs_active + 1 <= :limit_docs

    so two uploads racing for the last slot or the last megabytes cannot both pass, and a refusal changes nothing. Raises
    `QuotaExceeded` with `kind` `storage` (the bytes do not fit) or `documents` (no slot left) and `{used, limit, plan}`;
    the caller adds `largest_documents`, which needs the document table.
    """
    ensure_usage(user_id)
    limits = limits_for(user_id)
    updated = QuotaUsage.objects.filter(
        user_id=user_id,
        bytes_used__lte=limits.storage_bytes - amount,
        docs_active__lte=limits.max_documents - 1,
    ).update(bytes_used=F("bytes_used") + amount, docs_active=F("docs_active") + 1, updated_at=timezone.now())
    if updated:
        return
    row = QuotaUsage.objects.filter(pk=user_id).values("bytes_used", "docs_active").first() or {}
    used_bytes, used_docs = row.get("bytes_used", 0), row.get("docs_active", 0)
    if document_limit_hit(used_bytes, used_docs, amount, limits) == "storage":
        raise _exceeded(user_id, "storage", used_bytes, limits.storage_bytes)
    raise _exceeded(user_id, "documents", used_docs, limits.max_documents)


def release_document(user_id, amount: int) -> None:
    """Gives back a document's bytes and its slot together (trash purge, expiry, rejection); clamps at zero."""
    QuotaUsage.objects.filter(pk=user_id).update(
        bytes_used=Greatest(F("bytes_used") - amount, Value(0)),
        docs_active=Greatest(F("docs_active") - 1, Value(0)),
        updated_at=timezone.now(),
    )


# Plan-limit accessors for the services that enforce them in code (the counters above enforce the rest in SQL).
def max_pages(user_id) -> int:
    return limits_for(user_id).max_pages


def max_documents(user_id) -> int:
    return limits_for(user_id).max_documents


def max_marks_per_document(user_id) -> int:
    return limits_for(user_id).max_marks_per_document


def ocr_pages_per_month(user_id) -> int:
    return limits_for(user_id).ocr_pages_per_month


def exports_per_month(user_id) -> int:
    return limits_for(user_id).exports_per_month


def charge_monthly(
    user_id, counter: str, amount: int = 1, limit: int | None = None, *, now: datetime | None = None
) -> None:
    """
    Conditional upsert on `(user, month)`, month in India time: the same one-statement rule as the lifetime counters.
    `limit` defaults to the plan's (`MONTHLY_LIMITS`); a counter with none (`uploads`) is only counted. Refused charges
    raise `QuotaExceeded` with `kind` the counter's name and change nothing.
    """
    month = month_start(now or timezone.now())
    limit_name = MONTHLY_LIMITS[counter]
    MonthlyUsage.objects.bulk_create([MonthlyUsage(user_id=user_id, month=month)], ignore_conflicts=True)
    rows = MonthlyUsage.objects.filter(user_id=user_id, month=month)
    if limit_name is None and limit is None:
        rows.update(**{counter: F(counter) + amount, "updated_at": timezone.now()})
        return
    limit = getattr(limits_for(user_id), limit_name) if limit is None else limit
    if not rows.filter(**{f"{counter}__lte": limit - amount}).update(
        **{counter: F(counter) + amount, "updated_at": timezone.now()}
    ):
        used = rows.values_list(counter, flat=True).first() or 0
        raise _exceeded(user_id, counter, used, limit)


def refund_monthly(user_id, counter: str, amount: int = 1, *, now: datetime | None = None) -> None:
    MonthlyUsage.objects.filter(user_id=user_id, month=month_start(now or timezone.now())).update(
        **{counter: Greatest(F(counter) - amount, Value(0)), "updated_at": timezone.now()}
    )
