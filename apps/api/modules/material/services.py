"""
Services for F-12 Institute Study Material (MAT).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, models, transaction
from django.utils import timezone

from core import events as core_events

from . import errors
from .domain import item_keys, labels, levels, matching, pages, progress as progress_domain, term
from .models import (
    AuditLog,
    Edition,
    EditionItem,
    ImportJob,
    Item,
    Progress,
    Provider,
    Report,
    Unit,
    UnitChapter,
    UserEdition,
    UserProvider,
    Work,
)


MATERIAL_MAX_PRIVATE_WORKS = 5
MATERIAL_MAX_PRIVATE_ITEMS = 1000
MATERIAL_MAX_CUSTOM_PROVIDERS = 20


# ==========================================
# Provider Lifecycle
# ==========================================

def create_provider(actor_id: uuid.UUID | None, payload: dict[str, Any]) -> Provider:
    """
    Creates an institute, coaching, or publisher provider.
    Deduplicates by normalised_name if an active or pending provider already exists.
    """
    name = payload["name"].strip()
    norm_name = labels.normalise_provider_name(name)
    kind = payload.get("kind", Provider.Kind.COACHING)

    existing = Provider.objects.filter(
        normalised_name=norm_name, status__in=[Provider.Status.ACTIVE, Provider.Status.PENDING]
    ).first()
    if existing:
        return existing

    slug = payload.get("slug")
    if not slug:
        slug = labels.normalise_label(name)
        if Provider.objects.filter(slug=slug).exists():
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    ingestion_source_id = payload.get("ingestion_source_id") or uuid.uuid4()
    is_custom = payload.get("is_custom", False)

    provider = Provider.objects.create(
        slug=slug,
        name=name,
        normalised_name=norm_name,
        kind=kind,
        ingestion_source_id=ingestion_source_id,
        status=Provider.Status.PENDING if is_custom else Provider.Status.ACTIVE,
        website_url=payload.get("website_url"),
        created_by_user_id=actor_id if is_custom else None,
    )

    AuditLog.objects.create(
        actor_id=actor_id,
        entity_type="provider",
        entity_id=provider.id,
        action="provider_create",
        after={"name": name, "slug": slug, "kind": kind, "status": provider.status},
    )

    return provider


def merge_provider(
    actor_id: uuid.UUID,
    source_provider_id: uuid.UUID,
    target_provider_id: uuid.UUID,
) -> Provider:
    """
    Merges source_provider into target_provider, re-pointing works and followers.
    """
    with transaction.atomic():
        source = Provider.objects.select_for_update().get(id=source_provider_id)
        target = Provider.objects.select_for_update().get(id=target_provider_id)

        # Re-point works
        Work.objects.filter(provider=source).update(provider=target)

        # Re-point user providers
        for up in UserProvider.objects.filter(provider=source):
            if not UserProvider.objects.filter(user_id=up.user_id, provider=target, relation=up.relation, course_title=up.course_title).exists():
                up.provider = target
                up.save(update_fields=["provider", "updated_at"])
            else:
                up.delete()

        source.status = Provider.Status.MERGED
        source.merged_into = target
        source.save(update_fields=["status", "merged_into", "updated_at"])

        AuditLog.objects.create(
            actor_id=actor_id,
            entity_type="provider",
            entity_id=source.id,
            action="provider_merge",
            before={"provider_id": str(source.id)},
            after={"merged_into_id": str(target.id)},
        )

    return target


def set_followed_providers(
    user_id: uuid.UUID,
    provider_ids: list[uuid.UUID],
    custom_names: list[str] | None = None,
) -> list[Provider]:
    """
    Sets followed providers for a student (e.g. from onboarding or settings).
    Creates pending providers for custom typed names.
    """
    followed: list[Provider] = []
    custom_names = custom_names or []

    # Check custom provider quota
    existing_custom_count = Provider.objects.filter(created_by_user_id=user_id).count()
    if existing_custom_count + len(custom_names) > MATERIAL_MAX_CUSTOM_PROVIDERS:
        raise errors.QuotaExceeded("Custom provider limit reached.")

    with transaction.atomic():
        # Handle explicit provider IDs
        for p_id in provider_ids:
            prov = Provider.objects.filter(id=p_id).first()
            if prov and prov.status in (Provider.Status.ACTIVE, Provider.Status.PENDING):
                UserProvider.objects.get_or_create(
                    user_id=user_id,
                    provider=prov,
                    relation=UserProvider.Relation.FOLLOWS,
                    defaults={"created_via": "settings"},
                )
                followed.append(prov)

        # Handle custom names
        for c_name in custom_names:
            c_name = c_name.strip()
            if not c_name:
                continue
            prov = create_provider(
                actor_id=user_id,
                payload={"name": c_name, "kind": Provider.Kind.COACHING, "is_custom": True},
            )
            UserProvider.objects.get_or_create(
                user_id=user_id,
                provider=prov,
                relation=UserProvider.Relation.FOLLOWS,
                defaults={"created_via": "onboarding"},
            )
            if prov not in followed:
                followed.append(prov)

    return followed


# ==========================================
# Work Lifecycle
# ==========================================

def create_work(actor_id: uuid.UUID, payload: dict[str, Any]) -> Work:
    """
    Creates a new public study material work.
    """
    provider_id = payload["provider_id"]
    work_key = payload["work_key"].strip()
    title = payload["title"].strip()

    provider = Provider.objects.get(id=provider_id)

    work = Work.objects.create(
        provider=provider,
        work_key=work_key,
        title=title,
        kind=payload.get("kind", Work.Kind.MODULE),
        base_work_id=payload.get("base_work_id"),
        course_id=payload["course_id"],
        level_id=payload["level_id"],
        subject_key=payload["subject_key"],
        subject_id=payload.get("subject_id"),
        visibility=Work.Visibility.PUBLIC,
        status=Work.Status.ACTIVE,
    )

    AuditLog.objects.create(
        actor_id=actor_id,
        entity_type="work",
        entity_id=work.id,
        action="work_create",
        after={"work_key": work_key, "title": title},
    )

    return work


def create_private_work(user_id: uuid.UUID, payload: dict[str, Any]) -> Work:
    """
    Creates a private checklist work for a student (FR-F12-40).
    """
    current_count = Work.objects.filter(
        owner_user_id=user_id, status=Work.Status.ACTIVE, deleted_at__isnull=True
    ).count()
    if current_count >= MATERIAL_MAX_PRIVATE_WORKS:
        raise errors.QuotaExceeded("Private checklist limit reached (maximum 5).")

    provider = Provider.objects.filter(id=payload.get("provider_id")).first()
    if not provider:
        provider = Provider.objects.filter(slug="icai").first() or Provider.objects.first()

    title = payload["title"].strip()
    work_key = f"chk-{uuid.uuid4().hex[:8]}"

    work = Work.objects.create(
        provider=provider,
        work_key=work_key,
        title=title,
        kind=Work.Kind.CHECKLIST,
        course_id=payload["course_id"],
        level_id=payload["level_id"],
        subject_key=payload["subject_key"],
        subject_id=payload.get("subject_id"),
        owner_user_id=user_id,
        visibility=Work.Visibility.PRIVATE,
        status=Work.Status.ACTIVE,
    )

    # Automatically create default current edition for private checklist
    edition = Edition.objects.create(
        work=work,
        label="Personal Checklist",
        applies_from_term="2020-01",
        applies_from_ord=term.term_to_ord("2020-01"),
        status=Edition.Status.CURRENT,
        published_at=timezone.now(),
        published_by=user_id,
    )

    AuditLog.objects.create(
        actor_id=user_id,
        entity_type="work",
        entity_id=work.id,
        action="private_work_create",
        after={"title": title, "edition_id": str(edition.id)},
    )

    return work


# ==========================================
# Edition Lifecycle
# ==========================================

def create_draft_edition(
    actor_id: uuid.UUID,
    work_id: uuid.UUID,
    payload: dict[str, Any],
) -> Edition:
    """
    Creates a draft edition for a work.
    Copies unit and chapter mappings from the previous edition if one exists.
    """
    work = Work.objects.get(id=work_id)
    label = payload["label"].strip()
    applies_from = payload["applies_from_term"].strip()
    applies_to = payload.get("applies_to_term")
    if applies_to:
        applies_to = applies_to.strip()

    from_ord, to_ord = term.validate_term_range(applies_from, applies_to)

    with transaction.atomic():
        edition = Edition.objects.create(
            work=work,
            label=label,
            edition_date=payload.get("edition_date"),
            reprint_date=payload.get("reprint_date"),
            applies_from_term=applies_from,
            applies_to_term=applies_to,
            applies_from_ord=from_ord,
            applies_to_ord=to_ord,
            applicability_note=payload.get("applicability_note", ""),
            status=Edition.Status.DRAFT,
            source_url=payload.get("source_url"),
            source_page_url=payload.get("source_page_url"),
            page_offset=payload.get("page_offset", 0),
        )

        # Copy units from previous edition if exists
        prev_edition = Edition.objects.filter(
            work=work, status__in=[Edition.Status.CURRENT, Edition.Status.SUPERSEDED]
        ).order_by("-applies_from_ord").first()

        if prev_edition:
            for prev_u in prev_edition.units.all():
                new_u = Unit.objects.create(
                    edition=edition,
                    unit_key=prev_u.unit_key,
                    module_label=prev_u.module_label,
                    printed_number=prev_u.printed_number,
                    title=prev_u.title,
                    page_start=prev_u.page_start,
                    page_end=prev_u.page_end,
                    sort_order=prev_u.sort_order,
                )
                for uc in prev_u.chapter_mappings.all():
                    UnitChapter.objects.create(
                        unit=new_u,
                        chapter_id=uc.chapter_id,
                        subject_key=uc.subject_key,
                        chapter_key=uc.chapter_key,
                        scheme_id=uc.scheme_id,
                        is_primary=uc.is_primary,
                        status=UnitChapter.Status.CONFIRMED,
                        origin=UnitChapter.Origin.COPIED,
                        confidence=Decimal("1.00"),
                    )

        AuditLog.objects.create(
            actor_id=actor_id,
            entity_type="edition",
            entity_id=edition.id,
            action="edition_draft_create",
            after={"label": label, "work_id": str(work.id)},
        )

    return edition


def import_index(
    actor_id: uuid.UUID,
    edition_id: uuid.UUID,
    items_data: list[dict[str, Any]],
    units_data: list[dict[str, Any]] | None = None,
) -> ImportJob:
    """
    Imports an index of items (and optional units) for an edition.
    Idempotent by (work, unit_key, kind, label_norm).
    """
    with transaction.atomic():
        edition = Edition.objects.select_for_update().get(id=edition_id)
        work = edition.work

        if edition.status not in (Edition.Status.DRAFT, Edition.Status.MATCHING):
            raise errors.StaleEditionError("Can only import items into draft or matching editions.")

        # 1. Upsert Units
        units_by_key = {u.unit_key: u for u in edition.units.all()}
        if units_data:
            for u_data in units_data:
                u_key = u_data["unit_key"].strip()
                if u_key not in units_by_key:
                    unit_obj = Unit.objects.create(
                        edition=edition,
                        unit_key=u_key,
                        module_label=u_data.get("module_label", ""),
                        printed_number=u_data.get("printed_number", ""),
                        title=u_data.get("title", ""),
                        page_start=u_data.get("page_start"),
                        page_end=u_data.get("page_end"),
                        sort_order=u_data.get("sort_order", 0),
                    )
                    units_by_key[u_key] = unit_obj

        # 2. Process Items
        created_items = 0
        updated_items = 0

        # Existing sequence tracker for stable item_key generation
        existing_keys = set(Item.objects.filter(work=work).values_list("item_key", flat=True))
        max_seq = len(existing_keys)

        for pos, it_data in enumerate(items_data, start=1):
            unit_key = it_data["unit_key"].strip()
            unit_obj = units_by_key.get(unit_key)
            if not unit_obj:
                unit_obj = Unit.objects.create(
                    edition=edition,
                    unit_key=unit_key,
                    title=it_data.get("unit_title", f"Unit {unit_key}"),
                    sort_order=pos,
                )
                units_by_key[unit_key] = unit_obj

            printed_label = it_data["printed_label"].strip()
            label_norm = labels.normalise_label(printed_label)
            kind = it_data.get("kind", Item.Kind.ILLUSTRATION)
            descriptor = it_data.get("descriptor", "").strip() or None
            match_hash = item_keys.compute_content_hash(kind, descriptor)
            printed_ord = labels.extract_ordinal(printed_label)

            # Find or create stable Item identity
            item_obj = None
            candidate_key = it_data.get("item_key")
            if candidate_key:
                item_obj = Item.objects.filter(work=work, item_key=candidate_key).first()

            if not item_obj:
                # Try matching by existing item with same kind and unit in work
                max_seq += 1
                gen_key = item_keys.make_item_key(unit_key, kind, max_seq)
                item_obj = Item.objects.create(
                    work=work,
                    item_key=gen_key,
                    kind=kind,
                    status=Item.Status.ACTIVE,
                    first_edition=edition,
                    created_by=actor_id,
                )
                created_items += 1
            else:
                updated_items += 1

            # Create or update EditionItem
            EditionItem.objects.update_or_create(
                edition=edition,
                item=item_obj,
                defaults={
                    "unit": unit_obj,
                    "printed_label": printed_label,
                    "label_norm": label_norm,
                    "printed_ordinal": printed_ord,
                    "page_start": it_data.get("page_start"),
                    "page_end": it_data.get("page_end"),
                    "position": pos * 1024,
                    "descriptor": descriptor,
                    "chapter_id": it_data.get("chapter_id") or uuid.uuid4(),
                    "topic_id": it_data.get("topic_id"),
                    "subject_key": it_data.get("subject_key") or work.subject_key,
                    "chapter_key": it_data.get("chapter_key", ""),
                    "map_status": EditionItem.MapStatus.CONFIRMED if it_data.get("chapter_id") else EditionItem.MapStatus.SUGGESTED,
                    "change_kind": EditionItem.ChangeKind.NEW,
                    "match_hash": match_hash,
                },
            )

        edition.status = Edition.Status.MATCHING
        edition.save(update_fields=["status", "updated_at"])

        job = ImportJob.objects.create(
            edition=edition,
            user_id=actor_id,
            format="json",
            status=ImportJob.Status.IMPORTED,
            counts={
                "v": 1,
                "rows": len(items_data),
                "created": created_items,
                "updated": updated_items,
            },
            finished_at=timezone.now(),
        )

    return job


def run_matching(actor_id: uuid.UUID, edition_id: uuid.UUID) -> dict[str, Any]:
    """
    Compares editionitems against previous edition using domain matching rules.
    """
    with transaction.atomic():
        edition = Edition.objects.select_for_update().get(id=edition_id)
        work = edition.work

        prev_edition = Edition.objects.filter(
            work=work, status__in=[Edition.Status.CURRENT, Edition.Status.SUPERSEDED]
        ).exclude(id=edition.id).order_by("-applies_from_ord").first()

        if not prev_edition:
            # First edition: everything is new and confirmed
            edition.items.all().update(
                change_kind=EditionItem.ChangeKind.NEW,
                match_method=EditionItem.MatchMethod.NEW,
                match_confidence=Decimal("1.00"),
                match_status=EditionItem.MatchStatus.CONFIRMED,
            )
            edition.status = Edition.Status.READY
            counts = {"v": 1, "same": 0, "edited": 0, "renumbered": 0, "new": edition.items.count(), "removed": 0}
            edition.counts = counts
            edition.save(update_fields=["status", "counts", "updated_at"])
            return counts

        # Fetch previous and new rows
        prev_rows = [
            {
                "id": str(it.id),
                "item_id": str(it.item_id),
                "kind": it.item.kind,
                "label_norm": it.label_norm,
                "match_hash": it.match_hash,
                "descriptor": it.descriptor,
                "position": it.position,
            }
            for it in prev_edition.items.select_related("item").filter(status=EditionItem.Status.ACTIVE)
        ]

        new_rows = [
            {
                "id": str(it.id),
                "kind": it.item.kind,
                "label_norm": it.label_norm,
                "match_hash": it.match_hash,
                "descriptor": it.descriptor,
                "position": it.position,
            }
            for it in edition.items.select_related("item").all()
        ]

        candidates = matching.match_units_items(prev_rows, new_rows)

        diff_counts = {"v": 1, "same": 0, "edited": 0, "renumbered": 0, "new": 0, "removed": 0}

        for cand in candidates:
            diff_counts[cand.change_kind] = diff_counts.get(cand.change_kind, 0) + 1
            if cand.new_row_temp_id:
                EditionItem.objects.filter(id=cand.new_row_temp_id).update(
                    change_kind=cand.change_kind,
                    match_method=cand.match_method,
                    match_confidence=Decimal(str(cand.match_confidence)),
                    match_status=cand.match_status,
                    previous_id=cand.previous_row_id,
                )

        needs_review_count = edition.items.filter(match_status=EditionItem.MatchStatus.NEEDS_REVIEW).count()
        unmapped_count = edition.items.filter(map_status__in=[EditionItem.MapStatus.SUGGESTED, EditionItem.MapStatus.REJECTED]).count()

        if needs_review_count == 0 and unmapped_count == 0:
            edition.status = Edition.Status.READY
        else:
            edition.status = Edition.Status.MATCHING

        edition.counts = diff_counts
        edition.save(update_fields=["status", "counts", "updated_at"])

    return diff_counts


def decide_match(
    actor_id: uuid.UUID,
    edition_item_id: uuid.UUID,
    decision: str,
    target_item_id: uuid.UUID | None = None,
) -> EditionItem:
    """
    Reviewer decides match: 'same', 'renamed', 'new', 'removed', 'split'.
    """
    with transaction.atomic():
        item_row = EditionItem.objects.select_for_update().get(id=edition_item_id)
        before_state = {"change_kind": item_row.change_kind, "match_status": item_row.match_status}

        item_row.match_status = EditionItem.MatchStatus.CONFIRMED
        item_row.match_method = EditionItem.MatchMethod.MANUAL
        item_row.match_confidence = Decimal("1.00")

        if decision == "same":
            item_row.change_kind = EditionItem.ChangeKind.SAME
        elif decision == "renamed":
            item_row.change_kind = EditionItem.ChangeKind.RENUMBERED
        elif decision == "new":
            item_row.change_kind = EditionItem.ChangeKind.NEW
            item_row.previous_id = None
        elif decision == "removed":
            item_row.change_kind = EditionItem.ChangeKind.REMOVED
            item_row.status = EditionItem.Status.REMOVED

        if target_item_id:
            item_row.item_id = target_item_id

        item_row.save(update_fields=["change_kind", "match_status", "match_method", "match_confidence", "previous_id", "status", "updated_at"])

        AuditLog.objects.create(
            actor_id=actor_id,
            entity_type="edition_item",
            entity_id=item_row.id,
            action="match_decide",
            before=before_state,
            after={"decision": decision, "change_kind": item_row.change_kind},
        )

    return item_row


def publish_edition(actor_id: uuid.UUID, edition_id: uuid.UUID) -> Edition:
    """
    Publishes an edition atomically.
    Ensures term non-overlap, supersedes previous overlapping current editions,
    updates work cached level and item counts, and emits material_edition_published.
    """
    with transaction.atomic():
        edition = Edition.objects.select_for_update().select_related("work", "work__provider").get(id=edition_id)
        work = edition.work
        now = timezone.now()

        # Check mapping and matching integrity
        unmapped = edition.items.filter(
            status=EditionItem.Status.ACTIVE,
            map_status__in=[EditionItem.MapStatus.SUGGESTED, EditionItem.MapStatus.REJECTED],
        ).count()
        if unmapped > 0:
            raise errors.MappingIncompleteError(f"{unmapped} items have incomplete chapter mappings.")

        needs_review = edition.items.filter(match_status=EditionItem.MatchStatus.NEEDS_REVIEW).count()
        if needs_review > 0:
            raise errors.StaleEditionError(f"{needs_review} items still need matching review.")

        # Supersede older overlapping current editions
        Edition.objects.filter(
            work=work,
            status=Edition.Status.CURRENT,
        ).exclude(id=edition.id).update(
            status=Edition.Status.SUPERSEDED,
            superseded_at=now,
        )

        # Compute capabilities and materialisation level
        # Default baseline capabilities for provider
        caps = ["metadata", "link_out"]
        lvl = levels.level_for(caps)

        edition.status = Edition.Status.CURRENT
        edition.published_at = now
        edition.published_by = actor_id
        edition.capabilities_at_publish = caps
        edition.level_at_publish = lvl
        edition.save(
            update_fields=[
                "status",
                "published_at",
                "published_by",
                "capabilities_at_publish",
                "level_at_publish",
                "updated_at",
            ]
        )

        # Update cached work counters
        active_count = edition.items.filter(status=EditionItem.Status.ACTIVE).count()
        work.item_count_cached = active_count
        work.level_cached = lvl
        work.save(update_fields=["item_count_cached", "level_cached", "updated_at"])

        AuditLog.objects.create(
            actor_id=actor_id,
            entity_type="edition",
            entity_id=edition.id,
            action="edition_publish",
            after={"status": "current", "level": lvl, "items": active_count},
        )

        # Emit domain event
        core_events.emit_domain_event(
            "material_edition_published",
            {
                "work_id": str(work.id),
                "edition_id": str(edition.id),
                "applies_from": edition.applies_from_term,
                "counts": edition.counts,
                "subject_key": work.subject_key,
                "course_id": str(work.course_id),
                "level_id": str(work.level_id),
            },
            actor_id=actor_id,
        )

    return edition


def withdraw_edition(
    actor_id: uuid.UUID,
    edition_id: uuid.UUID,
    reason: str = Edition.WithdrawReason.EDITORIAL,
) -> Edition:
    """
    Withdraws a published edition (e.g. rights lapsed, takedown, editorial).
    """
    with transaction.atomic():
        edition = Edition.objects.select_for_update().get(id=edition_id)
        edition.status = Edition.Status.WITHDRAWN
        edition.withdraw_reason = reason
        edition.save(update_fields=["status", "withdraw_reason", "updated_at"])

        AuditLog.objects.create(
            actor_id=actor_id,
            entity_type="edition",
            entity_id=edition.id,
            action="edition_withdraw",
            after={"reason": reason},
        )

        core_events.emit_domain_event(
            "material_edition_withdrawn",
            {
                "edition_id": str(edition.id),
                "reason": reason,
            },
            actor_id=actor_id,
        )

    return edition


def restore_edition(actor_id: uuid.UUID, edition_id: uuid.UUID) -> Edition:
    """
    Restores a withdrawn edition back to current.
    """
    with transaction.atomic():
        edition = Edition.objects.select_for_update().get(id=edition_id)
        edition.status = Edition.Status.CURRENT
        edition.withdraw_reason = None
        edition.save(update_fields=["status", "withdraw_reason", "updated_at"])

        AuditLog.objects.create(
            actor_id=actor_id,
            entity_type="edition",
            entity_id=edition.id,
            action="edition_restore",
            after={"status": "current"},
        )

    return edition


# ==========================================
# Student Progress
# ==========================================

def set_progress(
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    edition_id: uuid.UUID,
    state: str,
    *,
    note: str = "",
    client_ts: datetime | None = None,
    self_declared: bool = False,
) -> Progress:
    """
    Idempotent, offline-capable student progress write with Last-Writer-Wins semantics (FR-F12-26).
    Emits material_progress_changed domain event.
    """
    now = timezone.now()
    client_ts = client_ts or now

    item = Item.objects.get(id=item_id)
    edition = Edition.objects.get(id=edition_id)

    # Fetch match_hash from current edition item to store as content_stamp
    ed_item = EditionItem.objects.filter(edition=edition, item=item).first()
    stamp = ed_item.match_hash if ed_item else None
    chapter_id = ed_item.chapter_id if ed_item else uuid.uuid4()

    with transaction.atomic():
        existing = Progress.objects.filter(user_id=user_id, item=item).first()

        # Last writer wins check
        if existing and existing.client_ts and client_ts < existing.client_ts:
            return existing

        done_at = existing.done_at if existing else None
        if state == Progress.State.DONE and not done_at:
            done_at = now

        progress_obj, _ = Progress.objects.update_or_create(
            user_id=user_id,
            item=item,
            defaults={
                "edition": edition,
                "state": state,
                "note": note,
                "done_at": done_at,
                "content_stamp": stamp,
                "self_declared": self_declared,
                "client_ts": client_ts,
            },
        )

        # Emit progress event
        core_events.emit_domain_event(
            "material_progress_changed",
            {
                "user_id": str(user_id),
                "item_id": str(item.id),
                "chapter_id": str(chapter_id),
                "state": state,
                "self_declared": self_declared,
            },
            user_id=user_id,
        )

    return progress_obj


def set_progress_batch(
    user_id: uuid.UUID,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Replays batched offline progress marks (max 100).
    """
    results = []
    for it in items[:100]:
        item_id = it["item_id"]
        edition_id = it["edition_id"]
        state = it["state"]
        note = it.get("note", "")
        client_ts_str = it.get("client_ts")
        client_ts = None
        if client_ts_str:
            try:
                client_ts = datetime.fromisoformat(client_ts_str)
            except Exception:
                client_ts = None

        try:
            p = set_progress(
                user_id=user_id,
                item_id=item_id,
                edition_id=edition_id,
                state=state,
                note=note,
                client_ts=client_ts,
                self_declared=it.get("self_declared", False),
            )
            results.append({"item_id": str(item_id), "status": "ok", "state": p.state})
        except Exception as exc:
            results.append({"item_id": str(item_id), "status": "error", "error": str(exc)})

    return results


def set_user_edition(
    user_id: uuid.UUID,
    work_id: uuid.UUID,
    edition_id: uuid.UUID | None,
) -> UserEdition:
    """
    Saves student's explicit edition preference for a work.
    """
    work = Work.objects.get(id=work_id)
    edition = Edition.objects.get(id=edition_id) if edition_id else None

    user_ed, _ = UserEdition.objects.update_or_create(
        user_id=user_id,
        work=work,
        defaults={"edition": edition},
    )
    return user_ed


def dismiss_banner(
    user_id: uuid.UUID,
    work_id: uuid.UUID,
    edition_id: uuid.UUID,
    days: int = 30,
) -> UserEdition:
    """
    Dismisses the new-edition banner for a work for 30 days.
    """
    work = Work.objects.get(id=work_id)
    until = timezone.now() + timedelta(days=days)

    user_ed, _ = UserEdition.objects.update_or_create(
        user_id=user_id,
        work=work,
        defaults={
            "banner_dismissed_for_edition_id": edition_id,
            "banner_dismissed_until": until,
        },
    )
    return user_ed


def submit_report(
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    edition_id: uuid.UUID,
    kind: str,
    message: str = "",
) -> Report:
    """
    Submits a report on an item (wrong page, dead link, etc.).
    One open report per kind per item per student.
    """
    item = Item.objects.get(id=item_id)
    edition = Edition.objects.get(id=edition_id)

    rep, _ = Report.objects.update_or_create(
        item=item,
        reporter_user_id=user_id,
        kind=kind,
        status=Report.Status.OPEN,
        defaults={
            "edition": edition,
            "message": message[:500],
        },
    )
    return rep


# ==========================================
# DPDP Export & Erasure
# ==========================================

def delete_all_for_user(user_id: uuid.UUID) -> dict[str, int]:
    """
    Deletes all student personal study material data (DPDP compliance).
    Nulls created_by_user_id on pending custom providers.
    """
    with transaction.atomic():
        progress_del = Progress.objects.filter(user_id=user_id).count()
        Progress.objects.filter(user_id=user_id).delete()

        uprov_del = UserProvider.objects.filter(user_id=user_id).count()
        UserProvider.objects.filter(user_id=user_id).delete()

        ued_del = UserEdition.objects.filter(user_id=user_id).count()
        UserEdition.objects.filter(user_id=user_id).delete()

        # Delete private checklist works owned by the user
        private_works = list(Work.objects.filter(owner_user_id=user_id, kind=Work.Kind.CHECKLIST))
        private_del = len(private_works)
        for pw in private_works:
            pw.delete()

        rep_del = Report.objects.filter(reporter_user_id=user_id).count()
        Report.objects.filter(reporter_user_id=user_id).delete()

        # Detach user identity from any pending custom providers
        Provider.objects.filter(created_by_user_id=user_id).update(created_by_user_id=None)

    return {
        "progress": progress_del,
        "user_providers": uprov_del,
        "user_editions": ued_del,
        "private_works": private_del,
        "reports": rep_del,
    }


def export_for_user(user_id: uuid.UUID) -> dict[str, Any]:
    """
    Exports student study material history and preferences (DPDP).
    """
    progress_qs = Progress.objects.filter(user_id=user_id).select_related("item", "edition")
    providers_qs = UserProvider.objects.filter(user_id=user_id).select_related("provider")
    editions_qs = UserEdition.objects.filter(user_id=user_id).select_related("work", "edition")

    return {
        "progress": [
            {
                "item_key": p.item.item_key,
                "state": p.state,
                "note": p.note,
                "done_at": p.done_at.isoformat() if p.done_at else None,
                "edition_label": p.edition.label,
                "self_declared": p.self_declared,
            }
            for p in progress_qs
        ],
        "followed_providers": [
            {
                "provider_slug": up.provider.slug,
                "provider_name": up.provider.name,
                "relation": up.relation,
                "course_title": up.course_title,
                "purchased_on": up.purchased_on.isoformat() if up.purchased_on else None,
            }
            for up in providers_qs
        ],
        "chosen_editions": [
            {
                "work_key": ue.work.work_key,
                "work_title": ue.work.title,
                "edition_label": ue.edition.label if ue.edition else None,
            }
            for ue in editions_qs
        ],
    }
