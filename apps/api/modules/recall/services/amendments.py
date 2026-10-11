"""
The amendment port (R2-W2, FR-F15-49). F-14 is not built, so recall subscribes to its three events by NAME and never imports it
(`subscribers.py`); each handler only queues a `recall.flag_amendment` job. The job runs in two stages, both idempotent:

  platform  platform items whose `reference_keys` share a provision key with the event (the chapter match when the event carries
            no `provision_keys`, a PROPOSED F-14 extension) get a `RecallAmendmentFlag` row: the "Under review after amendment"
            ribbon for everyone. A retraction deletes the rows its amendment made.
  own       her OWN cards whose item has a matching reference key (chunks of 1,000) get `needs_recheck` with reason `amendment` and
            `recheck_ref` = the amendment id: a "Check against amendment" chip she dismisses with "Still correct". Memory is never
            touched: no schedule event, no reset, no change of due. A retraction clears the chips it set (and only those).

The job key is the event key, so a redelivered event queues nothing new. Payloads hold ids and provision keys (statute references),
never card text.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from core import jobs as core_jobs

from ..domain import amendments as domain
from ..models import RecallAmendmentFlag, RecallCard, RecallItem

logger = logging.getLogger(__name__)

JOB_FLAG_AMENDMENT = "recall.flag_amendment"


def _uuid(value) -> UUID | None:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _chapter_ids(payload: dict) -> list[str]:
    raw = list(payload.get("chapter_ids") or [])
    raw += [c.get("chapter_id") for c in payload.get("chapters") or [] if isinstance(c, dict)]
    return sorted({str(u) for u in (_uuid(r) for r in raw) if u is not None})


def queue_event(kind: str, payload: dict) -> bool:
    """Queue the flag job for one F-14 event. False when the event is not for us (a non-material correction, a bad payload)."""
    material = payload.get("material")
    amendment_id = _uuid(payload.get("amendment_id"))
    if amendment_id is None or not domain.is_relevant(kind, material=material if isinstance(material, bool) else None):
        return False
    revision_id = _uuid(payload.get("revision_id"))
    key = domain.event_key(kind, amendment_id, revision_id)
    body = {
        "kind": kind,
        "amendment_id": str(amendment_id),
        "revision_id": str(revision_id) if revision_id else None,
        "chapter_ids": _chapter_ids(payload),
        "provision_keys": domain.normalise_keys(payload.get("provision_keys")),
        "event_key": key,
        "stage": "platform",
        "after": None,
    }
    core_jobs.enqueue(JOB_FLAG_AMENDMENT, body, dedupe_key=f"{JOB_FLAG_AMENDMENT}:{key}:platform", once=True)
    return True


def _matching_item_ids(
    ownership: str, keys: list[str], chapter_ids: list[str], after: UUID | None, limit: int
) -> list[UUID]:
    """Ids of the items (platform or hers) that match, in id order after `after`, at most `limit`."""
    qs = RecallItem.objects.filter(ownership=ownership).exclude(status__in=("deleted", "withdrawn"))
    if after is not None:
        qs = qs.filter(id__gt=after)
    if not keys:
        if ownership != "platform" or not chapter_ids:
            return []
        return list(qs.filter(chapter_id__in=chapter_ids).order_by("id").values_list("id", flat=True)[:limit])
    if connection.vendor == "postgresql":
        return list(qs.filter(reference_keys__has_any_keys=keys).order_by("id").values_list("id", flat=True)[:limit])
    wanted = set(keys)
    out: list[UUID] = []
    for item_id, ref_keys in (
        qs.exclude(reference_keys=[]).order_by("id").values_list("id", "reference_keys").iterator()
    ):
        if wanted & set(domain.normalise_keys(ref_keys)):
            out.append(item_id)
            if len(out) >= limit:
                break
    return out


def _flag_platform(payload: dict, now: datetime) -> int:
    amendment_id = UUID(payload["amendment_id"])
    keys, chapters = payload["provision_keys"], payload["chapter_ids"]
    revision = _uuid(payload.get("revision_id"))
    total, after = 0, None
    while True:
        ids = _matching_item_ids("platform", keys, chapters, after, domain.FLAG_CHUNK)
        if not ids:
            return total
        RecallAmendmentFlag.objects.bulk_create(
            [RecallAmendmentFlag(item_id=i, amendment_id=amendment_id, revision_id=revision) for i in ids],
            ignore_conflicts=True,
        )
        RecallItem.objects.filter(pk__in=ids, needs_editor_check=False).update(
            needs_editor_check=True, check_reason="amendment", check_ref=str(amendment_id), updated_at=now
        )
        total += len(ids)
        if len(ids) < domain.FLAG_CHUNK:
            return total
        after = ids[-1]


def _unflag_platform(payload: dict, now: datetime) -> int:
    amendment_id = UUID(payload["amendment_id"])
    item_ids = list(RecallAmendmentFlag.objects.filter(amendment_id=amendment_id).values_list("item_id", flat=True))
    RecallAmendmentFlag.objects.filter(amendment_id=amendment_id).delete()
    for item_id in item_ids:
        other = RecallAmendmentFlag.objects.filter(item_id=item_id).values_list("amendment_id", flat=True).first()
        if other is not None:
            RecallItem.objects.filter(pk=item_id, check_reason="amendment").update(check_ref=str(other), updated_at=now)
        else:
            RecallItem.objects.filter(pk=item_id, check_reason="amendment").update(
                needs_editor_check=False, check_reason=None, check_ref=None, updated_at=now
            )
    return len(item_ids)


def _flag_own(payload: dict, after: UUID | None, now: datetime) -> tuple[int, UUID | None]:
    """One chunk: the cards of up to 1,000 of her own items that match. Returns (cards flagged, cursor of the next chunk or None)."""
    ids = _matching_item_ids("user", payload["provision_keys"], [], after, domain.FLAG_CHUNK)
    if not ids:
        return 0, None
    flagged = RecallCard.objects.filter(
        item_id__in=ids, status__in=("active", "suspended"), needs_recheck=False
    ).update(
        needs_recheck=True,
        recheck_reason="amendment",
        recheck_ref=payload["amendment_id"],
        rev=F("rev") + 1,
        updated_at=now,
    )
    return flagged, (ids[-1] if len(ids) == domain.FLAG_CHUNK else None)


def _clear_own(payload: dict, after: UUID | None, now: datetime) -> tuple[int, UUID | None]:
    qs = RecallCard.objects.filter(recheck_reason="amendment", recheck_ref=payload["amendment_id"], needs_recheck=True)
    if after is not None:
        qs = qs.filter(id__gt=after)
    ids = list(qs.order_by("id").values_list("id", flat=True)[: domain.FLAG_CHUNK])
    if not ids:
        return 0, None
    cleared = RecallCard.objects.filter(pk__in=ids).update(
        needs_recheck=False, recheck_reason=None, recheck_ref=None, rev=F("rev") + 1, updated_at=now
    )
    return cleared, (ids[-1] if len(ids) == domain.FLAG_CHUNK else None)


def run_job(payload: dict) -> dict:
    """The handler of `recall.flag_amendment`: one stage per job so each fits a tick, and a redelivery changes nothing."""
    now = timezone.now()
    kind, key = payload["kind"], payload["event_key"]
    retract = kind == domain.RETRACTED
    after = _uuid(payload.get("after"))
    with transaction.atomic():
        if payload.get("stage") == "platform":
            platform = _unflag_platform(payload, now) if retract else _flag_platform(payload, now)
            _queue_own(payload, key, None)
            return {"platform_items": platform}
        done, nxt = (_clear_own if retract else _flag_own)(payload, after, now)
        if nxt is not None:
            _queue_own(payload, key, nxt)
    return {"cards": done, "more": nxt is not None}


def _queue_own(payload: dict, key: str, after: UUID | None) -> None:
    body = {**payload, "stage": "own", "after": str(after) if after else None}
    core_jobs.enqueue(JOB_FLAG_AMENDMENT, body, dedupe_key=f"{JOB_FLAG_AMENDMENT}:{key}:own:{after or 0}", once=True)


__all__ = ["JOB_FLAG_AMENDMENT", "queue_event", "run_job"]
