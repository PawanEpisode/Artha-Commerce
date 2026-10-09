"""
Delete-all and export for one student (FR-F15-75, PRD 7, ERD 7). Registered with `core.registry` in `RecallConfig.ready()`, so
account deletion and account export reach recall without `profiles` importing it, and also callable on their own from the
recall settings screen. Both stay open with the `recall_system` flag off (D4): a rollout switch must never block erasure.

`delete_all_for_user` removes every row the student owns, in dependency order: the review log (under the `recall.erasing`
switch that lifts the immutability trigger for this one transaction), schedule events, sessions, cards, subscriptions, her own
decks and items with their versions, rollups, settings, her own parameter sets, usage counters and the reports she sent. It is
idempotent and reports counts. Platform decks and items belong to the platform and are never touched. `recall_auditlog` rows
whose actor is this id stay (staff actions are an accountability record, hold ids and counts only, and never student text).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from ..models import (
    RecallCard,
    RecallChapterRollup,
    RecallDailyRollup,
    RecallDeck,
    RecallItem,
    RecallItemVersion,
    RecallParams,
    RecallQuotaUsage,
    RecallReport,
    RecallReviewLog,
    RecallScheduleEvent,
    RecallSession,
    RecallSettings,
    RecallSubscription,
)
from . import log_guard

CONFIRM_WORD = "ERASE"


def _count(qs) -> int:
    return qs.delete()[0]


def delete_all_for_user(user_id) -> dict:
    """Erase everything recall holds for the student. Returns `{table_name: rows_deleted}`."""
    report: dict[str, int] = {}
    with transaction.atomic():
        with log_guard.erasing():
            report["reviewlog"] = _count(RecallReviewLog.objects.filter(user_id=user_id))
        report["scheduleevents"] = _count(RecallScheduleEvent.objects.filter(user_id=user_id))
        report["sessions"] = _count(RecallSession.objects.filter(user_id=user_id))
        report["cards"] = _count(RecallCard.objects.filter(user_id=user_id))
        report["subscriptions"] = _count(RecallSubscription.objects.filter(user_id=user_id))
        own_items = RecallItem.objects.filter(ownership="user", owner_user_id=user_id)
        report["item_versions"] = _count(RecallItemVersion.objects.filter(item__in=own_items))
        report["items"] = _count(RecallItem.objects.filter(ownership="user", owner_user_id=user_id))
        report["decks"] = _count(RecallDeck.objects.filter(kind="user", owner_user_id=user_id))
        report["daily_rollups"] = _count(RecallDailyRollup.objects.filter(user_id=user_id))
        report["chapter_rollups"] = _count(RecallChapterRollup.objects.filter(user_id=user_id))
        report["settings"] = _count(RecallSettings.objects.filter(pk=user_id))
        report["params"] = _count(RecallParams.objects.filter(scope="user", user_id=user_id))
        report["quota"] = _count(RecallQuotaUsage.objects.filter(pk=user_id))
        report["reports"] = _count(RecallReport.objects.filter(reporter_user_id=user_id))
    return report


# ---------------------------------------------------------------------------------------------- export


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) or hasattr(value, "isoformat") else value


def _row(values: dict) -> dict:
    return {
        k: (str(v) if k.endswith("_id") or k == "id" else _iso(v)) if v is not None else None for k, v in values.items()
    }


CARD_COLUMNS = (
    "id", "item_id", "ordinal", "subscription_id", "item_version_id", "chapter_id", "subject_key", "importance", "state",
    "step", "stability", "difficulty", "due_at", "last_review_at", "reps", "lapses", "leech", "status", "created_at",
)  # fmt: skip
REVIEW_COLUMNS = (
    "id", "kind", "card_id", "item_id", "item_version_id", "session_id", "rating", "reviewed_at", "received_at",
    "duration_ms", "mode", "counts_for_scheduling", "device_id", "tz_offset_min", "local_date", "voids_id", "flags",
)  # fmt: skip
CHUNK = 2000


def export_for_user(user_id) -> dict:
    """Everything recall holds for the student, JSON ready: settings, cards, her own items, decks, subscriptions, sessions, reviews."""
    settings_row = RecallSettings.objects.filter(pk=user_id).values().first()
    own_items = list(RecallItem.objects.filter(ownership="user", owner_user_id=user_id).order_by("created_at", "id"))
    versions: dict = {}
    for v in RecallItemVersion.objects.filter(item__in=own_items).order_by("item_id", "version_no"):
        versions.setdefault(v.item_id, []).append(
            {"version_no": v.version_no, "state": v.state, "fields": v.fields, "created_at": _iso(v.created_at)}
        )
    decks = []
    for deck in RecallDeck.objects.filter(kind="user", owner_user_id=user_id).order_by("created_at", "id"):
        decks.append(
            {
                "id": str(deck.id),
                "title": deck.title,
                "description": deck.description,
                "status": deck.status,
                "item_ids": [str(i) for i in deck.members.order_by("position").values_list("item_id", flat=True)],
            }
        )
    return {
        "version": 1,
        "exported_at": _iso(timezone.now()),
        "settings": _row(settings_row) if settings_row else None,
        "cards": [
            _row(r)
            for r in RecallCard.objects.filter(user_id=user_id).order_by("created_at", "id").values(*CARD_COLUMNS)
        ],
        "items": [
            {
                "id": str(i.id),
                "kind": i.kind,
                "importance": i.importance,
                "status": i.status,
                "tags": i.tags,
                "reference_keys": i.reference_keys,
                "chapter_key": i.chapter_key,
                "subject_key": i.subject_key,
                "created_at": _iso(i.created_at),
                "versions": versions.get(i.id, []),
            }
            for i in own_items
        ],
        "decks": decks,
        "subscriptions": [
            _row(r)
            for r in RecallSubscription.objects.filter(user_id=user_id)
            .order_by("subscribed_at", "id")
            .values("id", "deck_id", "status", "unlock_mode", "min_importance", "subscribed_at", "archived_at")
        ],
        "sessions": [
            _row(r)
            for r in RecallSession.objects.filter(user_id=user_id)
            .order_by("started_at", "id")
            .values(
                "id",
                "source",
                "status",
                "started_at",
                "ended_at",
                "local_date",
                "reviewed",
                "new_count",
                "again",
                "hard",
                "good",
                "easy",
                "active_seconds",
            )  # fmt: skip
        ],
        "reviews": [_row(r) for r in _reviews(user_id)],
        "reports": [
            _row(r)
            for r in RecallReport.objects.filter(reporter_user_id=user_id)
            .order_by("created_at", "id")
            .values("id", "target_kind", "target_id", "reason", "note", "status", "created_at")
        ],
    }


def _reviews(user_id):
    """Every review, oldest first, read in keyset chunks so memory stays flat however long her history is."""
    last: tuple | None = None
    while True:
        qs = RecallReviewLog.objects.filter(user_id=user_id)
        if last is not None:
            from django.db.models import Q

            qs = qs.filter(Q(reviewed_at__gt=last[0]) | Q(reviewed_at=last[0], id__gt=last[1]))
        rows = list(qs.order_by("reviewed_at", "id").values(*REVIEW_COLUMNS)[:CHUNK])
        yield from rows
        if len(rows) < CHUNK:
            return
        last = (rows[-1]["reviewed_at"], rows[-1]["id"])
