"""
Read-only queries and selectors for F-14 Amendments (ERD Section 3.2).
Strictly separates public data from internal/editor data.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, TypedDict

from django.db.models import Q

from modules.coverage import selectors as coverage_selectors
from modules.syllabus.models import Level, Subject

from .domain.applicability import DocumentTermRule, evaluate_applicability
from .models import (
    Amendment,
    CardState,
    Change,
    ChangeMap,
    ChangeVersion,
    Revision,
    RevisionTerm,
)

LAW_LABELS: dict[str, str] = {
    "cgst": "CGST Act, 2017",
    "igst": "IGST Act, 2017",
    "utgst": "UTGST Act, 2017",
    "it-act": "Income-tax Act, 1961",
    "companies-act": "Companies Act, 2013",
    "fema": "Foreign Exchange Management Act, 1999",
    "sebi": "SEBI Regulations",
    "sa": "Standards on Auditing",
    "as": "Accounting Standards",
    "indas": "Indian Accounting Standards (Ind AS)",
    "cost-standards": "Cost Accounting Standards",
    "icsi-ss": "ICSI Secretarial Standards",
}


def get_law_label(law_key: str) -> str:
    return LAW_LABELS.get(law_key.lower(), law_key.upper() if law_key else "")


def get_card_applicability(
    student_term: str | None,
    terms: Any,
    effective_from_term_code: str | None,
) -> tuple[str, str]:
    rules = [
        DocumentTermRule(
            term_code=t.term_code,
            applicability=t.applicability,
            cutoff_date=t.cutoff_date,
            cutoff_note=t.cutoff_note,
        )
        for t in terms
    ]
    res = evaluate_applicability(student_term, rules, effective_from_term_code or None)
    return res.status.value, res.reason_code


class ViewerCtx(TypedDict):
    """
    Student viewer context derived from their active coverage enrollment.
    """

    user_id: uuid.UUID
    enrollment_id: uuid.UUID
    level_id: uuid.UUID
    scheme_id: uuid.UUID
    term_code: str | None
    subject_keys: list[str]


def get_viewer_context(user_id: uuid.UUID) -> ViewerCtx | None:
    """
    Builds the viewer context for an authenticated student from their active coverage enrollment.
    """
    enrollment = coverage_selectors.get_active_enrollment(user_id)
    if not enrollment:
        return None

    scheme = enrollment.scheme
    subjects = Subject.objects.filter(scheme=scheme, is_active=True).values_list("key", flat=True)

    return ViewerCtx(
        user_id=user_id,
        enrollment_id=enrollment.id,
        level_id=enrollment.level_id,
        scheme_id=enrollment.scheme_id,
        term_code=enrollment.target_term.code if enrollment.target_term else None,
        subject_keys=list(subjects),
    )


# ---------------------------------------------------------------------------
# Student Selectors
# ---------------------------------------------------------------------------


def my_summary(viewer: ViewerCtx) -> dict[str, Any]:
    """
    Summary of applicable amendments, review progress, and breakdown for student dashboard.
    """
    live_revisions = list(
        Revision.objects.filter(
            state=Revision.State.LIVE,
            amendment__level_id=viewer["level_id"],
            subjects__subject_key__in=viewer["subject_keys"],
        )
        .prefetch_related("terms", "subjects")
        .distinct()
    )

    if not live_revisions:
        return {
            "target_term": viewer["term_code"],
            "total_cards_count": 0,
            "reviewed_count": 0,
            "saved_count": 0,
            "breakdown_by_paper": [],
            "breakdown_by_type": {},
        }

    rev_ids = [r.id for r in live_revisions]
    rev_by_id = {r.id: r for r in live_revisions}

    cards = list(
        ChangeVersion.objects.filter(revision_id__in=rev_ids, is_live=True)
        .select_related("change")
        .prefetch_related("maps")
    )

    change_ids = [c.change_id for c in cards]
    card_states = {
        cs.change_id: cs for cs in CardState.objects.filter(user_id=viewer["user_id"], change_id__in=change_ids)
    }

    total_applicable = 0
    reviewed_applicable = 0
    saved_count = 0
    paper_counts: dict[str, dict[str, int]] = {}
    type_counts: dict[str, int] = {}

    for c in cards:
        rev = rev_by_id[c.revision_id]
        app_state, _ = get_card_applicability(viewer["term_code"], rev.terms.all(), c.effective_from_term_code)

        state = card_states.get(c.change_id)
        is_reviewed = bool(state and state.reviewed_at)
        is_saved = bool(state and state.saved)
        if is_saved:
            saved_count += 1

        if app_state in ("applies", "unknown"):
            total_applicable += 1
            if is_reviewed:
                reviewed_applicable += 1

            type_counts[c.change_type] = type_counts.get(c.change_type, 0) + 1

            # Paper breakdown
            primary_map = next((m for m in c.maps.all() if m.is_primary), None)
            subj_key = primary_map.subject_key if primary_map else None
            if not subj_key:
                first_subj = rev.subjects.first()
                subj_key = first_subj.subject_key if first_subj else "other"

            if subj_key not in paper_counts:
                paper_counts[subj_key] = {"total": 0, "reviewed": 0}
            paper_counts[subj_key]["total"] += 1
            if is_reviewed:
                paper_counts[subj_key]["reviewed"] += 1

    paper_breakdown = [
        {"subject_key": k, "total": v["total"], "reviewed": v["reviewed"]} for k, v in paper_counts.items()
    ]

    return {
        "target_term": viewer["term_code"],
        "total_cards_count": total_applicable,
        "reviewed_count": reviewed_applicable,
        "saved_count": saved_count,
        "breakdown_by_paper": paper_breakdown,
        "breakdown_by_type": type_counts,
    }


def my_changes(
    viewer: ViewerCtx,
    flt: dict[str, Any],
    *,
    cursor: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Filtered list of cards for the student with applicability and review state computed.
    """
    applies_filter = flt.get("applies", "mine")  # "mine" (applies/unknown) or "all"
    subject_filter = flt.get("subject")
    type_filter = flt.get("type")
    state_filter = flt.get("state")  # "unreviewed", "reviewed", "saved"
    q_search = flt.get("q", "").strip().lower()

    target_subjects = [subject_filter] if subject_filter else viewer["subject_keys"]

    live_revisions = list(
        Revision.objects.filter(
            state=Revision.State.LIVE,
            amendment__level_id=viewer["level_id"],
            subjects__subject_key__in=target_subjects,
        )
        .prefetch_related("terms", "subjects", "amendment")
        .distinct()
    )

    if not live_revisions:
        return {"cards": [], "total_count": 0, "has_more": False}

    rev_by_id = {r.id: r for r in live_revisions}
    rev_ids = list(rev_by_id.keys())

    query = Q(revision_id__in=rev_ids, is_live=True)
    if type_filter:
        query &= Q(change_type=type_filter)

    cards = list(
        ChangeVersion.objects.filter(query)
        .select_related("change", "revision__amendment")
        .prefetch_related("maps")
        .order_by("-revision__issued_on", "source_page", "title")
    )

    change_ids = [c.change_id for c in cards]
    card_states = {
        cs.change_id: cs for cs in CardState.objects.filter(user_id=viewer["user_id"], change_id__in=change_ids)
    }

    result_cards = []
    for c in cards:
        # Search query matching
        if q_search:
            matches = (
                q_search in c.title.lower()
                or (c.law_key and q_search in c.law_key.lower())
                or q_search in get_law_label(c.law_key).lower()
                or q_search in c.provision_label.lower()
                or any(q_search in k.lower() for k in c.provision_keys)
            )
            if not matches:
                continue

        rev = rev_by_id[c.revision_id]
        app_state, app_reason = get_card_applicability(viewer["term_code"], rev.terms.all(), c.effective_from_term_code)

        if applies_filter == "mine" and app_state == "not_applicable":
            continue

        state = card_states.get(c.change_id)
        is_reviewed = bool(state and state.reviewed_at)
        is_saved = bool(state and state.saved)
        is_updated = bool(
            state
            and state.reviewed_version_id
            and state.reviewed_version_id != c.id
            and c.revision_effect == ChangeVersion.RevisionEffect.UPDATED
        )

        if state_filter == "reviewed" and not is_reviewed:
            continue
        if state_filter == "unreviewed" and is_reviewed:
            continue
        if state_filter == "saved" and not is_saved:
            continue

        primary_map = next((m for m in c.maps.all() if m.is_primary), None)
        subject_key = primary_map.subject_key if primary_map else ""

        result_cards.append(
            {
                "public_id": c.change.public_id,
                "card_key": c.change.card_key,
                "change_type": c.change_type,
                "law_label": get_law_label(c.law_key),
                "provision_label": c.provision_label,
                "title": c.title,
                "summary_old": c.summary_old,
                "summary_new": c.summary_new,
                "effective_text": f"Applicable from {c.effective_from_term_code}" if c.effective_from_term_code else "",
                "source_page": c.source_page,
                "materiality": c.materiality,
                "revision_effect": c.revision_effect,
                "subject_key": subject_key,
                "applicability": {
                    "state": app_state,
                    "reason": app_reason,
                },
                "is_reviewed": is_reviewed,
                "is_saved": is_saved,
                "is_updated": is_updated,
                "document": {
                    "slug": rev.amendment.slug,
                    "title": rev.amendment.title,
                    "official_url": rev.official_url,
                    "issued_on": rev.issued_on.isoformat() if rev.issued_on else None,
                },
                "mappings": [
                    {
                        "subject_key": m.subject_key,
                        "chapter_key": m.chapter_key,
                        "is_primary": m.is_primary,
                    }
                    for m in c.maps.all()
                ],
            }
        )

    # Simple pagination
    offset = int(cursor) if cursor and cursor.isdigit() else 0
    paged = result_cards[offset : offset + limit]
    has_more = (offset + limit) < len(result_cards)
    next_cursor = str(offset + limit) if has_more else None

    return {
        "cards": paged,
        "total_count": len(result_cards),
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


def my_change(viewer: ViewerCtx, public_id: str) -> dict[str, Any] | None:
    """
    Card detail for a student, including user interaction state and coverage status on affected chapters.
    """
    change = (
        Change.objects.filter(public_id=public_id)
        .select_related("live_version__revision__amendment", "amendment")
        .first()
    )
    if not change or not change.live_version:
        return None

    # Check level scope
    if change.amendment.level_id != viewer["level_id"]:
        return None

    cv = change.live_version
    rev = cv.revision

    # Check paper scope
    rev_subject_keys = set(rev.subjects.values_list("subject_key", flat=True))
    if not (rev_subject_keys & set(viewer["subject_keys"])):
        return None

    app_state, app_reason = get_card_applicability(viewer["term_code"], rev.terms.all(), cv.effective_from_term_code)

    state = CardState.objects.filter(user_id=viewer["user_id"], change=change).first()
    is_reviewed = bool(state and state.reviewed_at)
    is_saved = bool(state and state.saved)
    is_updated = bool(
        state
        and state.reviewed_version_id
        and state.reviewed_version_id != cv.id
        and cv.revision_effect == ChangeVersion.RevisionEffect.UPDATED
    )

    # Chapter mappings and student's coverage status
    mappings_data = []
    for m in cv.maps.filter(status=ChangeMap.Status.CONFIRMED).select_related("chapter"):
        chp_data = {
            "subject_key": m.subject_key,
            "chapter_key": m.chapter_key,
            "chapter_name": m.chapter.name if m.chapter else "",
            "is_primary": m.is_primary,
            "coverage_pct": 0,
            "status": "not_started",
        }
        if m.chapter:
            progress = coverage_selectors.get_chapter_progress(viewer["user_id"], m.chapter.id)
            if progress:
                chp_data["coverage_pct"] = progress.coverage_pct
                chp_data["status"] = progress.status
        mappings_data.append(chp_data)

    return {
        "public_id": change.public_id,
        "card_key": change.card_key,
        "change_type": cv.change_type,
        "law_label": get_law_label(cv.law_key),
        "provision_label": cv.provision_label,
        "title": cv.title,
        "summary_old": cv.summary_old,
        "summary_new": cv.summary_new,
        "effective_text": f"Applicable from {cv.effective_from_term_code}" if cv.effective_from_term_code else "",
        "effective_from_term_code": cv.effective_from_term_code,
        "source_page": cv.source_page,
        "materiality": cv.materiality,
        "revision_effect": cv.revision_effect,
        "applicability": {
            "state": app_state,
            "reason": app_reason,
        },
        "is_reviewed": is_reviewed,
        "reviewed_at": state.reviewed_at.isoformat() if state and state.reviewed_at else None,
        "is_saved": is_saved,
        "is_updated": is_updated,
        "document": {
            "slug": rev.amendment.slug,
            "title": rev.amendment.title,
            "official_url": rev.official_url,
            "issued_on": rev.issued_on.isoformat() if rev.issued_on else None,
            "issuer_label": rev.amendment.issuer_label,
        },
        "mappings": mappings_data,
        "terms": [
            {
                "term_code": t.term_code,
                "applicability": t.applicability,
                "cutoff_date": t.cutoff_date.isoformat() if t.cutoff_date else None,
            }
            for t in rev.terms.all()
        ],
    }


def changes_for_chapters(viewer: ViewerCtx | None, chapter_ids: Sequence[uuid.UUID]) -> dict[str, list[dict[str, Any]]]:
    """
    Returns live change cards mapped to given chapters, with applicability evaluated.
    """
    result: dict[str, list[dict[str, Any]]] = {str(cid): [] for cid in chapter_ids}
    if not chapter_ids:
        return result

    maps = list(
        ChangeMap.objects.filter(
            chapter_id__in=chapter_ids,
            status=ChangeMap.Status.CONFIRMED,
            change_version__is_live=True,
        )
        .select_related(
            "change_version__change",
            "change_version__revision__amendment",
        )
        .prefetch_related("change_version__revision__terms")
    )

    for m in maps:
        cv = m.change_version
        rev = cv.revision
        term_code = viewer["term_code"] if viewer else None
        app_state, app_reason = get_card_applicability(term_code, rev.terms.all(), cv.effective_from_term_code)

        card_dict = {
            "public_id": cv.change.public_id,
            "card_key": cv.change.card_key,
            "title": cv.title,
            "provision_label": cv.provision_label,
            "change_type": cv.change_type,
            "summary_new": cv.summary_new,
            "summary_old": cv.summary_old,
            "materiality": cv.materiality,
            "source_page": cv.source_page,
            "applicability": {
                "state": app_state,
                "reason": app_reason,
            },
            "document_slug": rev.amendment.slug,
            "official_url": rev.official_url,
        }
        cid_str = str(m.chapter_id)
        if cid_str in result:
            result[cid_str].append(card_dict)

    return result


def my_archive(viewer: ViewerCtx) -> list[dict[str, Any]]:
    """
    Term archive for the student's level and papers.
    """
    revisions = list(
        Revision.objects.filter(
            state=Revision.State.LIVE,
            amendment__level_id=viewer["level_id"],
            subjects__subject_key__in=viewer["subject_keys"],
        )
        .prefetch_related("terms", "change_versions")
        .distinct()
    )

    terms_map: dict[str, dict[str, Any]] = {}
    for rev in revisions:
        cards_count = rev.change_versions.filter(is_live=True).count()
        for t in rev.terms.all():
            code = t.term_code
            if code not in terms_map:
                terms_map[code] = {
                    "term_code": code,
                    "documents_count": 0,
                    "cards_count": 0,
                    "applicability": "applies" if code == viewer["term_code"] else "not_applicable",
                }
            terms_map[code]["documents_count"] += 1
            terms_map[code]["cards_count"] += cards_count

    return sorted(terms_map.values(), key=lambda x: x["term_code"], reverse=True)


# ---------------------------------------------------------------------------
# Public Selectors (Strict Allow-list / No Private Fields)
# ---------------------------------------------------------------------------


def public_level(course_code: str, level_code: str) -> dict[str, Any] | None:
    """
    Public hub for a level: terms with document counts and papers covered.
    """
    level = Level.objects.filter(code=level_code, course__code=course_code).select_related("course").first()
    if not level:
        return None

    revisions = list(
        Revision.objects.filter(
            state=Revision.State.LIVE,
            amendment__level=level,
            amendment__seo_indexable=True,
        )
        .prefetch_related("terms", "subjects", "change_versions")
        .distinct()
    )

    terms_data: dict[str, dict[str, Any]] = {}
    papers_data: dict[str, int] = {}

    for rev in revisions:
        live_cards = rev.change_versions.filter(is_live=True).count()
        for t in rev.terms.all():
            code = t.term_code
            if code not in terms_data:
                terms_data[code] = {"term_code": code, "document_count": 0, "card_count": 0}
            terms_data[code]["document_count"] += 1
            terms_data[code]["card_count"] += live_cards

        for s in rev.subjects.all():
            papers_data[s.subject_key] = papers_data.get(s.subject_key, 0) + live_cards

    latest_revs = revisions[:6] if revisions else []

    return {
        "course": {"code": level.course.code, "name": level.course.name},
        "level": {"code": level.code, "name": level.name},
        "terms": sorted(terms_data.values(), key=lambda x: x["term_code"], reverse=True),
        "papers": [{"subject_key": k, "card_count": v} for k, v in papers_data.items()],
        "latest_documents": [
            {
                "slug": r.amendment.slug,
                "title": r.amendment.title,
                "issuer_label": r.amendment.issuer_label,
                "issued_on": r.issued_on.isoformat() if r.issued_on else None,
                "official_url": r.official_url,
            }
            for r in latest_revs
        ],
    }


def public_term(course_code: str, level_code: str, term_code: str) -> dict[str, Any] | None:
    """
    Public term archive: papers, cut-off dates, and documents applicable to that term.
    """
    level = Level.objects.filter(code=level_code, course__code=course_code).select_related("course").first()
    if not level:
        return None

    term_rows = list(
        RevisionTerm.objects.filter(
            term_code=term_code,
            applicability=RevisionTerm.Applicability.APPLIES,
            revision__state=Revision.State.LIVE,
            revision__amendment__level=level,
            revision__amendment__seo_indexable=True,
        ).select_related("revision__amendment")
    )

    rev_ids = [t.revision_id for t in term_rows]
    revisions = list(
        Revision.objects.filter(id__in=rev_ids)
        .prefetch_related("subjects", "change_versions")
        .select_related("amendment")
    )

    papers_map: dict[str, int] = {}
    for r in revisions:
        cards_count = r.change_versions.filter(is_live=True).count()
        for s in r.subjects.all():
            papers_map[s.subject_key] = papers_map.get(s.subject_key, 0) + cards_count

    cutoff_dates = [
        {"cutoff_date": t.cutoff_date.isoformat(), "cutoff_note": t.cutoff_note} for t in term_rows if t.cutoff_date
    ]

    return {
        "course": {"code": level.course.code, "name": level.course.name},
        "level": {"code": level.code, "name": level.name},
        "term_code": term_code,
        "cutoff_dates": cutoff_dates,
        "papers": [{"subject_key": k, "card_count": v} for k, v in papers_map.items()],
        "documents": [
            {
                "slug": r.amendment.slug,
                "title": r.amendment.title,
                "issued_on": r.issued_on.isoformat() if r.issued_on else None,
                "official_url": r.official_url,
            }
            for r in revisions
        ],
    }


def public_paper(
    course_code: str,
    level_code: str,
    term_code: str,
    subject_key: str,
    *,
    change_type: str | None = None,
    limit: int = 50,
) -> dict[str, Any] | None:
    """
    Public paper amendments: live cards grouped by chapter.
    """
    level = Level.objects.filter(code=level_code, course__code=course_code).select_related("course").first()
    if not level:
        return None

    revisions = list(
        Revision.objects.filter(
            state=Revision.State.LIVE,
            amendment__level=level,
            amendment__seo_indexable=True,
            terms__term_code=term_code,
            terms__applicability=RevisionTerm.Applicability.APPLIES,
            subjects__subject_key=subject_key,
        )
        .prefetch_related("terms", "subjects")
        .distinct()
    )

    rev_ids = [r.id for r in revisions]
    query = Q(revision_id__in=rev_ids, is_live=True)
    if change_type:
        query &= Q(change_type=change_type)

    cards = list(
        ChangeVersion.objects.filter(query)
        .select_related("change", "revision__amendment")
        .prefetch_related("maps")
        .order_by("source_page", "title")[:limit]
    )

    chapters_map: dict[str, list[dict[str, Any]]] = {}
    paper_cards: list[dict[str, Any]] = []

    for c in cards:
        card_data = {
            "public_id": c.change.public_id,
            "card_key": c.change.card_key,
            "change_type": c.change_type,
            "law_label": get_law_label(c.law_key),
            "provision_label": c.provision_label,
            "title": c.title,
            "summary_old": c.summary_old,
            "summary_new": c.summary_new,
            "effective_text": f"Applicable from {c.effective_from_term_code}" if c.effective_from_term_code else "",
            "source_page": c.source_page,
            "document": {
                "slug": c.revision.amendment.slug,
                "title": c.revision.amendment.title,
                "official_url": c.revision.official_url,
            },
        }

        primary_map = next((m for m in c.maps.all() if m.is_primary), None)
        if primary_map and primary_map.chapter_key:
            ckey = primary_map.chapter_key
            if ckey not in chapters_map:
                chapters_map[ckey] = []
            chapters_map[ckey].append(card_data)
        else:
            paper_cards.append(card_data)

    grouped_chapters = [{"chapter_key": k, "cards": v} for k, v in chapters_map.items()]

    return {
        "course": {"code": level.course.code, "name": level.course.name},
        "level": {"code": level.code, "name": level.name},
        "term_code": term_code,
        "subject_key": subject_key,
        "grouped_by_chapter": grouped_chapters,
        "paper_level_cards": paper_cards,
        "total_cards": len(cards),
    }


def public_change(public_id: str) -> dict[str, Any] | None:
    """
    Public card detail with official attribution and verification notice.
    Tombstone if retracted. Never leaks evidence quote or anchor.
    """
    change = (
        Change.objects.filter(public_id=public_id)
        .select_related(
            "amendment__course",
            "amendment__level",
            "live_version__revision",
        )
        .first()
    )
    if not change:
        return None

    if change.status == Change.Status.WITHDRAWN or change.amendment.status == Amendment.Status.RETRACTED:
        return {
            "public_id": change.public_id,
            "tombstone": True,
            "status": "retracted",
            "message": "This amendment card has been retracted by the Institute or editorial review.",
        }

    cv = change.live_version
    if not cv:
        return None

    rev = cv.revision
    terms = [
        {
            "term_code": t.term_code,
            "applicability": t.applicability,
            "cutoff_date": t.cutoff_date.isoformat() if t.cutoff_date else None,
        }
        for t in rev.terms.all()
    ]

    chapters = [
        {
            "subject_key": m.subject_key,
            "chapter_key": m.chapter_key,
            "is_primary": m.is_primary,
        }
        for m in cv.maps.filter(status=ChangeMap.Status.CONFIRMED)
    ]

    return {
        "public_id": change.public_id,
        "card_key": change.card_key,
        "tombstone": False,
        "status": "active",
        "change_type": cv.change_type,
        "law_label": get_law_label(cv.law_key),
        "law_key": cv.law_key,
        "provision_label": cv.provision_label,
        "title": cv.title,
        "summary_old": cv.summary_old,
        "summary_new": cv.summary_new,
        "effective_text": f"Applicable from {cv.effective_from_term_code}" if cv.effective_from_term_code else "",
        "effective_from_term_code": cv.effective_from_term_code,
        "source_page": cv.source_page,
        "materiality": cv.materiality,
        "document": {
            "slug": change.amendment.slug,
            "title": change.amendment.title,
            "issuer_label": change.amendment.issuer_label,
            "official_url": rev.official_url,
            "issued_on": rev.issued_on.isoformat() if rev.issued_on else None,
        },
        "terms": terms,
        "chapters": chapters,
        "notice": "Always verify against the official Institute PDF. This summary is provided for reference only.",
    }


def public_document(slug: str) -> dict[str, Any] | None:
    """
    Public document overview: revision history, terms, and cards grouped by paper.
    """
    amendment = Amendment.objects.filter(slug=slug).select_related("course", "level", "live_revision").first()
    if not amendment:
        return None

    if amendment.status == Amendment.Status.RETRACTED:
        return {
            "slug": amendment.slug,
            "tombstone": True,
            "status": "retracted",
            "message": "This document was retracted.",
        }

    rev = amendment.live_revision
    if not rev:
        return None

    terms = [
        {
            "term_code": t.term_code,
            "applicability": t.applicability,
            "cutoff_date": t.cutoff_date.isoformat() if t.cutoff_date else None,
            "cutoff_note": t.cutoff_note,
        }
        for t in rev.terms.all()
    ]

    cards = list(
        ChangeVersion.objects.filter(revision=rev, is_live=True)
        .select_related("change")
        .prefetch_related("maps")
        .order_by("source_page", "title")
    )

    by_paper: dict[str, list[dict[str, Any]]] = {}
    for c in cards:
        primary_map = next((m for m in c.maps.all() if m.is_primary), None)
        skey = primary_map.subject_key if primary_map else "other"
        if skey not in by_paper:
            by_paper[skey] = []
        by_paper[skey].append(
            {
                "public_id": c.change.public_id,
                "title": c.title,
                "provision_label": c.provision_label,
                "change_type": c.change_type,
                "source_page": c.source_page,
            }
        )

    return {
        "slug": amendment.slug,
        "title": amendment.title,
        "short_title": amendment.short_title,
        "issuer_label": amendment.issuer_label,
        "kind": amendment.kind,
        "course": {"code": amendment.course.code, "name": amendment.course.name},
        "level": {"code": amendment.level.code, "name": amendment.level.name},
        "revision_no": rev.revision_no,
        "issued_on": rev.issued_on.isoformat() if rev.issued_on else None,
        "official_url": rev.official_url,
        "terms": terms,
        "papers": [{"subject_key": k, "cards": v} for k, v in by_paper.items()],
        "notice": "Always verify against the official Institute PDF.",
    }


def latest_documents(limit: int = 12) -> list[dict[str, Any]]:
    """
    Returns latest live amendments for the public hub.
    """
    amendments = list(
        Amendment.objects.filter(
            status=Amendment.Status.ACTIVE,
            live_revision__isnull=False,
            seo_indexable=True,
        )
        .select_related("course", "level", "live_revision")
        .order_by("-last_released_at", "-created_at")[:limit]
    )

    out = []
    for a in amendments:
        rev = a.live_revision
        card_count = rev.change_versions.filter(is_live=True).count()
        out.append(
            {
                "slug": a.slug,
                "title": a.title,
                "issuer_label": a.issuer_label,
                "kind": a.kind,
                "course": a.course.code,
                "level": a.level.code,
                "cards_count": card_count,
                "issued_on": rev.issued_on.isoformat() if rev.issued_on else None,
                "official_url": rev.official_url,
            }
        )
    return out


def sitemap_paths() -> list[dict[str, Any]]:
    """
    Generates all public sitemap paths with lastmod timestamps.
    """
    entries = [{"path": "/amendments", "lastmod": None}]

    amendments = list(
        Amendment.objects.filter(
            status=Amendment.Status.ACTIVE,
            live_revision__isnull=False,
            seo_indexable=True,
        ).select_related("course", "level", "live_revision")
    )

    levels_seen = set()
    for a in amendments:
        lvl_key = f"/amendments/{a.course.code}/{a.level.code}"
        if lvl_key not in levels_seen:
            levels_seen.add(lvl_key)
            entries.append({"path": lvl_key, "lastmod": a.last_released_at.isoformat() if a.last_released_at else None})

        entries.append(
            {
                "path": f"/amendments/documents/{a.slug}",
                "lastmod": a.last_released_at.isoformat() if a.last_released_at else None,
            }
        )

    # Live change cards
    live_cards = list(
        Change.objects.filter(
            status=Change.Status.ACTIVE,
            live_version__isnull=False,
            amendment__status=Amendment.Status.ACTIVE,
            amendment__seo_indexable=True,
        ).select_related("amendment")
    )
    for c in live_cards:
        entries.append(
            {
                "path": f"/amendments/cards/{c.public_id}",
                "lastmod": c.updated_at.isoformat(),
            }
        )

    return entries
