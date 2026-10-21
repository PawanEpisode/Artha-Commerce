"""
Selectors for F-12 Institute Study Material (MAT).
"""

from __future__ import annotations

import uuid
from typing import Any

from django.db import models
from django.utils import timezone

from .domain import pages, progress as progress_domain
from .models import (
    Edition,
    EditionItem,
    Item,
    Progress,
    Provider,
    UserEdition,
    UserProvider,
    Work,
)


def edition_for(user_id: uuid.UUID, work_id: uuid.UUID) -> Edition | None:
    """
    Resolves the active edition for a student on a work:
    1. Student's explicit choice in UserEdition.
    2. Fallback to the latest current edition.
    """
    user_ed = UserEdition.objects.filter(user_id=user_id, work_id=work_id).first()
    if user_ed and user_ed.edition:
        return user_ed.edition

    return (
        Edition.objects.filter(work_id=work_id, status=Edition.Status.CURRENT)
        .order_by("-applies_from_ord")
        .first()
    )


def list_works(
    user_id: uuid.UUID,
    *,
    subject_key: str | None = None,
    provider_slug: str | None = None,
    include_private: bool = True,
) -> list[dict[str, Any]]:
    """
    Lists study material works available to the student.
    """
    qs = Work.objects.select_related("provider").filter(status=Work.Status.ACTIVE)

    if not include_private:
        qs = qs.filter(visibility=Work.Visibility.PUBLIC)
    else:
        qs = qs.filter(
            models.Q(visibility=Work.Visibility.PUBLIC) | models.Q(owner_user_id=user_id)
        )

    if subject_key:
        qs = qs.filter(subject_key=subject_key)
    if provider_slug:
        qs = qs.filter(provider__slug=provider_slug)

    works = list(qs)
    work_ids = [w.id for w in works]

    # Pre-fetch user edition choices
    user_editions = {
        ue.work_id: ue.edition
        for ue in UserEdition.objects.filter(user_id=user_id, work_id__in=work_ids).select_related("edition")
    }

    results = []
    for w in works:
        chosen_ed = user_editions.get(w.id)
        if not chosen_ed:
            chosen_ed = (
                Edition.objects.filter(work=w, status=Edition.Status.CURRENT)
                .order_by("-applies_from_ord")
                .first()
            )

        results.append({
            "id": str(w.id),
            "work_key": w.work_key,
            "title": w.title,
            "kind": w.kind,
            "provider": {
                "slug": w.provider.slug,
                "name": w.provider.name,
                "kind": w.provider.kind,
            },
            "subject_key": w.subject_key,
            "visibility": w.visibility,
            "level": w.level_cached,
            "item_count": w.item_count_cached,
            "edition": {
                "id": str(chosen_ed.id),
                "label": chosen_ed.label,
                "applies_from_term": chosen_ed.applies_from_term,
                "applies_to_term": chosen_ed.applies_to_term,
                "source_url": chosen_ed.source_url,
            }
            if chosen_ed
            else None,
        })

    return results


def get_work(
    user_id: uuid.UUID,
    work_key: str,
    *,
    edition_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    """
    Returns work overview with resolved edition and chapter progress summary.
    """
    work = (
        Work.objects.select_related("provider")
        .filter(
            work_key=work_key,
            status=Work.Status.ACTIVE,
        )
        .filter(models.Q(visibility=Work.Visibility.PUBLIC) | models.Q(owner_user_id=user_id))
        .first()
    )
    if not work:
        return None

    if edition_id:
        edition = Edition.objects.filter(id=edition_id, work=work).first()
    else:
        edition = edition_for(user_id, work.id)

    if not edition:
        return None

    # Fetch active items for this edition
    ed_items = list(
        EditionItem.objects.filter(edition=edition, status=EditionItem.Status.ACTIVE).values(
            "id", "item_id", "chapter_id", "chapter_key", "kind", "match_hash"
        )
    )

    item_ids = [it["item_id"] for it in ed_items]
    user_progress = {
        str(p.item_id): {
            "state": p.state,
            "content_stamp": p.content_stamp,
            "revisited_at": p.revisited_at,
        }
        for p in Progress.objects.filter(user_id=user_id, item_id__in=item_ids)
    }

    # Group by chapter
    chapters_map: dict[str, list[dict[str, Any]]] = {}
    for it in ed_items:
        ch_key = it["chapter_key"] or str(it["chapter_id"])
        chapters_map.setdefault(ch_key, []).append(it)

    chapters_summary = []
    for ch_key, ch_items in chapters_map.items():
        summary = progress_domain.compute_chapter_summary(ch_items, user_progress)
        chapters_summary.append({
            "chapter_key": ch_key,
            "chapter_id": str(ch_items[0]["chapter_id"]),
            "summary": summary,
        })

    # Overall work summary
    overall_summary = progress_domain.compute_chapter_summary(ed_items, user_progress)

    # Banner check: newer current edition exists?
    newer_edition = (
        Edition.objects.filter(
            work=work,
            status=Edition.Status.CURRENT,
            applies_from_ord__gt=edition.applies_from_ord,
        )
        .order_by("-applies_from_ord")
        .first()
    )

    banner_data = None
    if newer_edition:
        # Check dismissal
        user_ed = UserEdition.objects.filter(user_id=user_id, work=work).first()
        is_dismissed = (
            user_ed
            and user_ed.banner_dismissed_for_edition_id == newer_edition.id
            and user_ed.banner_dismissed_until
            and user_ed.banner_dismissed_until > timezone.now()
        )
        if not is_dismissed:
            banner_data = {
                "newer_edition_id": str(newer_edition.id),
                "newer_edition_label": newer_edition.label,
                "applies_from_term": newer_edition.applies_from_term,
                "counts": newer_edition.counts,
            }

    return {
        "id": str(work.id),
        "work_key": work.work_key,
        "title": work.title,
        "kind": work.kind,
        "provider": {
            "slug": work.provider.slug,
            "name": work.provider.name,
            "kind": work.provider.kind,
        },
        "subject_key": work.subject_key,
        "level": work.level_cached,
        "edition": {
            "id": str(edition.id),
            "label": edition.label,
            "applies_from_term": edition.applies_from_term,
            "applies_to_term": edition.applies_to_term,
            "applicability_note": edition.applicability_note,
            "source_url": edition.source_url,
            "source_page_url": edition.source_page_url,
            "page_offset": edition.page_offset,
        },
        "banner": banner_data,
        "overall_summary": overall_summary,
        "chapters": chapters_summary,
    }


def items_for_chapter(
    user_id: uuid.UUID,
    work_key: str,
    chapter_key: str,
    *,
    edition_id: uuid.UUID | None = None,
    kind: str | None = None,
    state: str | None = None,
    q: str | None = None,
) -> list[dict[str, Any]]:
    """
    Returns active items of a chapter in the student's resolved edition, overlaid with progress.
    """
    work = (
        Work.objects.filter(work_key=work_key, status=Work.Status.ACTIVE)
        .filter(models.Q(visibility=Work.Visibility.PUBLIC) | models.Q(owner_user_id=user_id))
        .first()
    )
    if not work:
        return []

    edition = (
        Edition.objects.filter(id=edition_id, work=work).first()
        if edition_id
        else edition_for(user_id, work.id)
    )
    if not edition:
        return []

    qs = (
        EditionItem.objects.filter(
            edition=edition,
            chapter_key=chapter_key,
            status=EditionItem.Status.ACTIVE,
        )
        .select_related("item", "unit")
        .order_by("position")
    )

    if kind:
        qs = qs.filter(item__kind=kind)
    if q:
        qs = qs.filter(
            models.Q(printed_label__icontains=q) | models.Q(descriptor__icontains=q)
        )

    ed_items = list(qs)
    item_ids = [it.item_id for it in ed_items]

    # Pre-fetch student progress
    user_progress = {
        p.item_id: p
        for p in Progress.objects.filter(user_id=user_id, item_id__in=item_ids)
    }

    results = []
    for it in ed_items:
        prog = user_progress.get(it.item_id)
        current_state = prog.state if prog else "todo"

        if state and state != "all":
            if state == "todo" and prog is not None:
                continue
            elif state != "todo" and current_state != state:
                continue

        deep_link = pages.format_deep_link(
            edition.source_url, it.page_start, edition.page_offset
        )

        revised = progress_domain.is_revised_since_done(
            {
                "state": prog.state,
                "content_stamp": prog.content_stamp,
                "revisited_at": prog.revisited_at,
            }
            if prog
            else None,
            it.match_hash,
        )

        results.append({
            "id": str(it.id),
            "item_id": str(it.item_id),
            "item_key": it.item.item_key,
            "kind": it.item.kind,
            "printed_label": it.printed_label,
            "label_norm": it.label_norm,
            "unit": {
                "key": it.unit.unit_key,
                "title": it.unit.title,
                "printed_number": it.unit.printed_number,
            },
            "page_start": it.page_start,
            "page_end": it.page_end,
            "deep_link_url": deep_link,
            "descriptor": it.descriptor,
            "has_solution": bool(it.item.question_id),
            "change_kind": it.change_kind,
            "user_progress": {
                "state": current_state,
                "note": prog.note if prog else "",
                "done_at": prog.done_at.isoformat() if prog and prog.done_at else None,
                "revised_since_done": revised,
            },
        })

    return results


def chapter_summary(user_id: uuid.UUID, chapter_id: uuid.UUID) -> dict[str, Any]:
    """
    Ultra-fast chapter summary endpoint for the F-02 chapter page panel (Q-1).
    """
    # Find all active items for this chapter across current editions
    ed_items = list(
        EditionItem.objects.filter(
            chapter_id=chapter_id,
            status=EditionItem.Status.ACTIVE,
            edition__status=Edition.Status.CURRENT,
        )
        .select_related("item", "edition", "edition__work")
        .values("id", "item_id", "item__kind", "match_hash", "printed_label", "edition__work__work_key")
    )

    item_ids = [it["item_id"] for it in ed_items]
    user_progress = {
        str(p.item_id): {
            "state": p.state,
            "content_stamp": p.content_stamp,
            "revisited_at": p.revisited_at,
        }
        for p in Progress.objects.filter(user_id=user_id, item_id__in=item_ids)
    }

    formatted_items = [
        {"id": str(it["id"]), "item_id": str(it["item_id"]), "kind": it["item__kind"], "match_hash": it["match_hash"]}
        for it in ed_items
    ]

    summary = progress_domain.compute_chapter_summary(formatted_items, user_progress)

    # Next up item: first item with state == todo
    next_up = None
    for it in ed_items:
        s_id = str(it["item_id"])
        prog = user_progress.get(s_id)
        if not prog or prog.get("state") not in ("done", "skipped"):
            next_up = {
                "item_id": s_id,
                "edition_item_id": str(it["id"]),
                "printed_label": it["printed_label"],
                "work_key": it["edition__work__work_key"],
            }
            break

    return {
        "chapter_id": str(chapter_id),
        "summary": summary,
        "next_up": next_up,
    }


def get_item(
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    *,
    edition_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    """
    Returns full item detail: identity, printed labels per edition, locator, user state.
    """
    item = Item.objects.select_related("work", "work__provider").filter(id=item_id).first()
    if not item:
        return None

    # Resolve edition
    if edition_id:
        edition = Edition.objects.filter(id=edition_id, work=item.work).first()
    else:
        edition = edition_for(user_id, item.work_id)

    if not edition:
        return None

    current_ed_item = EditionItem.objects.filter(
        edition=edition, item=item
    ).select_related("unit").first()

    deep_link = None
    if current_ed_item:
        deep_link = pages.format_deep_link(
            edition.source_url, current_ed_item.page_start, edition.page_offset
        )

    prog = Progress.objects.filter(user_id=user_id, item=item).first()

    # Labels across all editions for history
    ed_history = [
        {
            "edition_label": ei.edition.label,
            "printed_label": ei.printed_label,
            "page": ei.page_start,
            "change_kind": ei.change_kind,
        }
        for ei in EditionItem.objects.filter(item=item).select_related("edition").order_by("-edition__applies_from_ord")
    ]

    return {
        "id": str(item.id),
        "item_key": item.item_key,
        "kind": item.kind,
        "work": {
            "work_key": item.work.work_key,
            "title": item.work.title,
            "provider_name": item.work.provider.name,
        },
        "current_edition": {
            "id": str(edition.id),
            "label": edition.label,
            "printed_label": current_ed_item.printed_label if current_ed_item else "",
            "page_start": current_ed_item.page_start if current_ed_item else None,
            "unit_title": current_ed_item.unit.title if current_ed_item else "",
            "deep_link_url": deep_link,
            "descriptor": current_ed_item.descriptor if current_ed_item else "",
            "has_solution": bool(item.question_id),
        },
        "history": ed_history,
        "user_progress": {
            "state": prog.state if prog else "todo",
            "note": prog.note if prog else "",
            "done_at": prog.done_at.isoformat() if prog and prog.done_at else None,
            "self_declared": prog.self_declared if prog else False,
        },
    }


def followed_providers(user_id: uuid.UUID) -> list[dict[str, Any]]:
    """
    Returns providers followed by student.
    """
    user_provs = UserProvider.objects.filter(
        user_id=user_id, archived_at__isnull=True
    ).select_related("provider")

    return [
        {
            "id": str(up.provider.id),
            "slug": up.provider.slug,
            "name": up.provider.name,
            "kind": up.provider.kind,
            "relation": up.relation,
            "course_title": up.course_title,
            "batch_label": up.batch_label,
            "purchased_on": up.purchased_on.isoformat() if up.purchased_on else None,
        }
        for up in user_provs
    ]


def compare_editions(
    work_key: str,
    from_edition_id: uuid.UUID,
    to_edition_id: uuid.UUID,
    *,
    chapter_key: str | None = None,
) -> list[dict[str, Any]]:
    """
    'What changed' view: diffs items between two editions of a work (FR-F12-39).
    """
    to_edition = Edition.objects.get(id=to_edition_id)

    qs = EditionItem.objects.filter(
        edition=to_edition,
    ).exclude(change_kind=EditionItem.ChangeKind.SAME).select_related("item", "previous_id")

    if chapter_key:
        qs = qs.filter(chapter_key=chapter_key)

    results = []
    for it in qs:
        results.append({
            "id": str(it.id),
            "item_key": it.item.item_key,
            "kind": it.item.kind,
            "printed_label": it.printed_label,
            "previous_label": it.previous_id.printed_label if it.previous_id else None,
            "change_kind": it.change_kind,
            "chapter_key": it.chapter_key,
            "descriptor": it.descriptor,
        })

    return results


def public_subject_material(
    course: str,
    level: str,
    subject: str,
) -> dict[str, Any]:
    """
    Public SEO facts: works, edition labels, applicability, official links, chapter lists.
    No student item text unless L4.
    """
    works = list(
        Work.objects.filter(
            subject_key=subject,
            visibility=Work.Visibility.PUBLIC,
            status=Work.Status.ACTIVE,
        ).select_related("provider")
    )

    works_data = []
    for w in works:
        current_ed = (
            Edition.objects.filter(work=w, status=Edition.Status.CURRENT)
            .order_by("-applies_from_ord")
            .first()
        )
        works_data.append({
            "work_key": w.work_key,
            "title": w.title,
            "provider": {"name": w.provider.name, "slug": w.provider.slug},
            "item_count": w.item_count_cached,
            "current_edition": {
                "label": current_ed.label,
                "applies_from_term": current_ed.applies_from_term,
                "applies_to_term": current_ed.applies_to_term,
                "applicability_note": current_ed.applicability_note,
                "source_page_url": current_ed.source_page_url,
            }
            if current_ed
            else None,
        })

    return {
        "course": course,
        "level": level,
        "subject": subject,
        "works": works_data,
    }
