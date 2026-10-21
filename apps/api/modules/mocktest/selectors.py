"""
Selectors for F-08 Mock Tests and MTP.
Read-only queries with permission scoping.
"""

from __future__ import annotations

import uuid
from typing import Any
from django.db.models import Q
from django.utils import timezone

from .domain import clock, percentile
from .models import (
    Attempt,
    AttemptSection,
    CohortStat,
    ExamFormat,
    Item,
    Paper,
    PaperVersion,
    Section,
    Series,
)


def list_papers(
    viewer_id: uuid.UUID | None,
    flt: dict[str, Any],
    *,
    order: str = "newest",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Lists papers matching filter:
    course, level, subject_key, series, term_code, source_tags, kinds, scheme, key, state, scope, q
    """
    qs = Paper.objects.select_related("series", "course", "level", "scheme", "subject")

    scope = flt.get("scope", "public")
    if scope == "mine" and viewer_id:
        qs = qs.filter(owner_user_id=viewer_id)
    else:
        # Default public visible
        if viewer_id:
            qs = qs.filter(Q(visibility=Paper.Visibility.PUBLIC, status=Paper.Status.LIVE) | Q(owner_user_id=viewer_id))
        else:
            qs = qs.filter(visibility=Paper.Visibility.PUBLIC, status=Paper.Status.LIVE)

    if flt.get("course"):
        qs = qs.filter(course__slug=flt["course"])
    if flt.get("level"):
        qs = qs.filter(level__slug=flt["level"])
    if flt.get("subject_key"):
        qs = qs.filter(subject_key=flt["subject_key"])
    if flt.get("series_slug"):
        qs = qs.filter(series__slug=flt["series_slug"])
    if flt.get("source_tags"):
        qs = qs.filter(source_tag__in=flt["source_tags"])
    if flt.get("kinds"):
        qs = qs.filter(kind__in=flt["kinds"])
    if flt.get("key_status"):
        qs = qs.filter(answer_key_status=flt["key_status"])
    if flt.get("q"):
        q_term = flt["q"].strip()
        qs = qs.filter(Q(title__icontains=q_term) | Q(description__icontains=q_term))

    if order == "newest":
        qs = qs.order_by("-released_at", "-created_at")
    else:
        qs = qs.order_by("created_at")

    papers = list(qs[:limit])

    # Overlay user attempt state if viewer_id is given
    attempt_map = {}
    if viewer_id and papers:
        user_attempts = Attempt.objects.filter(
            user_id=viewer_id,
            paper__in=papers,
        ).order_by("-created_at")
        for a in user_attempts:
            if a.paper_id not in attempt_map:
                attempt_map[a.paper_id] = {
                    "last_attempt_id": str(a.id),
                    "last_phase": a.phase,
                    "last_score": float(a.score) if a.score is not None else None,
                    "last_percent": float(a.percent) if a.percent is not None else None,
                }

    results = []
    for p in papers:
        results.append({
            "id": str(p.id),
            "public_id": p.public_id,
            "title": p.title,
            "slug": p.slug,
            "description": p.description,
            "kind": p.kind,
            "source_tag": p.source_tag,
            "visibility": p.visibility,
            "status": p.status,
            "delivery_mode": p.delivery_mode,
            "source_pdf_url": p.source_pdf_url,
            "solution_pdf_url": p.solution_pdf_url,
            "answer_key_status": p.answer_key_status,
            "syllabus_status": p.syllabus_status,
            "subject_key": p.subject_key,
            "series_title": p.series.title if p.series else None,
            "released_at": p.released_at.isoformat() if p.released_at else None,
            "attempt_count": p.attempt_count,
            "my_attempt": attempt_map.get(p.id),
        })

    return results


def get_paper(
    viewer_id: uuid.UUID | None,
    paper_id_or_public_id: str,
    *,
    version_no: int | None = None,
) -> dict[str, Any] | None:
    """
    Fetches paper detail with blueprint sections, choice groups and items.
    """
    try:
        p_uuid = uuid.UUID(paper_id_or_public_id)
        qs = Paper.objects.filter(id=p_uuid)
    except ValueError:
        qs = Paper.objects.filter(public_id=paper_id_or_public_id)

    paper = qs.select_related("series", "course", "level", "scheme", "subject").first()
    if not paper:
        return None

    # Check permission
    if paper.visibility == Paper.Visibility.PRIVATE and paper.owner_user_id != viewer_id:
        return None

    # Select version
    if version_no is not None:
        version = PaperVersion.objects.filter(paper=paper, version_no=version_no).first()
    elif paper.live_version_id:
        version = PaperVersion.objects.filter(id=paper.live_version_id).first()
    else:
        version = paper.versions.order_by("-version_no").first()

    sections = []
    items = []
    if version:
        sec_qs = version.sections.order_by("position")
        for sec in sec_qs:
            groups_data = [
                {
                    "key": g.key,
                    "label": g.label,
                    "required_count": g.required_count,
                    "overflow_policy": g.overflow_policy,
                }
                for g in sec.choice_groups.all()
            ]
            sections.append({
                "key": sec.key,
                "title": sec.title,
                "kind": sec.kind,
                "duration_seconds": sec.duration_seconds,
                "instructions_md": sec.instructions_md,
                "marks_total": float(sec.marks_total),
                "choice_groups": groups_data,
            })

        for it in version.items.select_related("section", "choice_group").order_by("position"):
            items.append({
                "position": it.position,
                "display_label": it.display_label,
                "question_id": str(it.question_id),
                "section_key": it.section.key,
                "choice_group_key": it.choice_group.key if it.choice_group else None,
                "marks": float(it.marks),
                "negative_marks": float(it.negative_marks) if it.negative_marks is not None else None,
                "suggested_seconds": it.suggested_seconds,
            })

    # My attempts history
    my_attempts = []
    if viewer_id:
        atts = Attempt.objects.filter(user_id=viewer_id, paper=paper).order_by("-created_at")
        my_attempts = [
            {
                "id": str(a.id),
                "attempt_no": a.attempt_no,
                "run_mode": a.run_mode,
                "phase": a.phase,
                "score": float(a.score) if a.score is not None else None,
                "max_score": float(a.max_score) if a.max_score is not None else None,
                "percent": float(a.percent) if a.percent is not None else None,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in atts
        ]

    return {
        "id": str(paper.id),
        "public_id": paper.public_id,
        "title": paper.title,
        "slug": paper.slug,
        "description": paper.description,
        "kind": paper.kind,
        "source_tag": paper.source_tag,
        "visibility": paper.visibility,
        "status": paper.status,
        "delivery_mode": paper.delivery_mode,
        "source_pdf_url": paper.source_pdf_url,
        "solution_pdf_url": paper.solution_pdf_url,
        "answer_key_status": paper.answer_key_status,
        "syllabus_status": paper.syllabus_status,
        "version": {
            "version_no": version.version_no if version else 1,
            "total_marks": float(version.total_marks) if version else 100.0,
            "duration_seconds": version.duration_seconds if version else 10800,
            "reading_seconds": version.reading_seconds if version else 0,
            "upload_window_seconds": version.upload_window_seconds if version else 0,
            "section_timing": version.section_timing if version else "none",
            "instructions_md": version.instructions_md if version else "",
            "sections": sections,
            "items": items,
        } if version else None,
        "my_attempts": my_attempts,
    }


def attempt_state(user_id: uuid.UUID, attempt_id: uuid.UUID) -> dict[str, Any] | None:
    """
    Returns full attempt state: clock, phase, sections, lease info, layout.
    """
    attempt = (
        Attempt.objects.filter(id=attempt_id, user_id=user_id)
        .select_related("paper", "paper_version")
        .first()
    )
    if not attempt:
        return None

    now = timezone.now()
    sec_dicts = [
        {"key": s.section.key, "status": s.status, "closes_at": s.closes_at}
        for s in attempt.sections.select_related("section")
    ]
    c_state = clock.state_at(
        phase=attempt.phase,
        instructions_accepted_at=attempt.instructions_accepted_at,
        reading_seconds=attempt.paper_version.reading_seconds,
        reading_ends_at=attempt.reading_ends_at,
        writing_started_at=attempt.writing_started_at,
        writing_ends_at=attempt.writing_ends_at,
        upload_until=attempt.upload_until,
        duration_seconds=attempt.paper_version.duration_seconds,
        extra_seconds=attempt.extra_seconds,
        paused_seconds=attempt.paused_seconds,
        is_paused=False,
        now=now,
        sections=sec_dicts,
        section_timing=attempt.paper_version.section_timing,
    )

    sections_data = [
        {
            "key": s.section.key,
            "title": s.section.title,
            "position": s.position,
            "status": s.status,
            "duration_seconds": s.section.duration_seconds,
            "opens_at": s.opens_at.isoformat() if s.opens_at else None,
            "closes_at": s.closes_at.isoformat() if s.closes_at else None,
        }
        for s in attempt.sections.select_related("section").order_by("position")
    ]

    return {
        "id": str(attempt.id),
        "paper_id": str(attempt.paper_id),
        "paper_title": attempt.paper.title,
        "run_mode": attempt.run_mode,
        "phase": c_state.phase,
        "server_time": now.isoformat(),
        "remaining_ms": c_state.remaining_ms,
        "section_remaining_ms": c_state.section_remaining_ms,
        "active_section_key": c_state.active_section_key,
        "lease_epoch": attempt.lease_epoch,
        "lease_label": attempt.lease_label,
        "last_position": attempt.last_position,
        "layout": attempt.layout,
        "sections": sections_data,
        "instructions_md": attempt.paper_version.instructions_md,
        "delivery_mode": attempt.paper.delivery_mode,
        "source_pdf_url": attempt.paper.source_pdf_url,
        "solution_pdf_url": attempt.paper.solution_pdf_url,
    }


def list_attempts(
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    paper_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Returns student's attempts history.
    """
    qs = Attempt.objects.filter(user_id=user_id, deleted_at__isnull=True).select_related(
        "paper", "paper_version"
    )
    if paper_id:
        qs = qs.filter(paper_id=paper_id)
    if status:
        qs = qs.filter(phase=status)

    qs = qs.order_by("-created_at")[:limit]

    return [
        {
            "id": str(a.id),
            "paper_id": str(a.paper_id),
            "paper_title": a.paper.title,
            "attempt_no": a.attempt_no,
            "run_mode": a.run_mode,
            "phase": a.phase,
            "score": float(a.score) if a.score is not None else None,
            "max_score": float(a.max_score) if a.max_score is not None else None,
            "percent": float(a.percent) if a.percent is not None else None,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            "created_at": a.created_at.isoformat(),
        }
        for a in qs
    ]


def result(user_id: uuid.UUID, attempt_id: uuid.UUID) -> dict[str, Any] | None:
    """
    Returns exam result summary, section breakdown and provisional status.
    """
    attempt = (
        Attempt.objects.filter(id=attempt_id, user_id=user_id)
        .select_related("paper", "paper_version")
        .first()
    )
    if not attempt:
        return None

    sections_res = [
        {
            "key": s.section.key,
            "title": s.section.title,
            "score": float(s.score) if s.score is not None else None,
            "max_score": float(s.max_score) if s.max_score is not None else None,
            "answered": s.answered,
            "correct": s.correct,
            "incorrect": s.incorrect,
            "skipped": s.skipped,
            "not_counted": s.not_counted,
            "time_spent_seconds": s.time_spent_seconds,
        }
        for s in attempt.sections.select_related("section").order_by("position")
    ]

    return {
        "id": str(attempt.id),
        "paper_id": str(attempt.paper_id),
        "paper_title": attempt.paper.title,
        "run_mode": attempt.run_mode,
        "phase": attempt.phase,
        "score": float(attempt.score) if attempt.score is not None else None,
        "max_score": float(attempt.max_score) if attempt.max_score is not None else None,
        "percent": float(attempt.percent) if attempt.percent is not None else None,
        "score_status": attempt.score_status or "final",
        "time_used_seconds": attempt.time_used_seconds,
        "integrity_class": attempt.integrity_class,
        "percentile_eligible": attempt.percentile_eligible,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        "source_pdf_url": attempt.paper.source_pdf_url,
        "solution_pdf_url": attempt.paper.solution_pdf_url,
        "sections": sections_res,
    }


def review(user_id: uuid.UUID, attempt_id: uuid.UUID, *, filter_by: str | None = None) -> dict[str, Any] | None:
    """
    Returns post-submit review with questions, student answers, keys and solutions.
    """
    attempt = Attempt.objects.filter(id=attempt_id, user_id=user_id).select_related("paper").first()
    if not attempt:
        return None
    if attempt.phase not in (Attempt.Phase.UPLOAD, Attempt.Phase.DONE):
        return None

    # Fetch review payload from practice
    from modules.practice.selectors import review_payload

    p_review = review_payload(user_id=user_id, session_id=attempt.session_id)

    items = p_review.get("items", []) if p_review else []
    if filter_by == "wrong":
        items = [it for it in items if it.get("result") == "incorrect"]
    elif filter_by == "skipped":
        items = [it for it in items if it.get("result") == "skipped"]
    elif filter_by == "flagged":
        items = [it for it in items if it.get("flagged")]

    return {
        "attempt_id": str(attempt.id),
        "paper_title": attempt.paper.title,
        "source_pdf_url": attempt.paper.source_pdf_url,
        "solution_pdf_url": attempt.paper.solution_pdf_url,
        "score": float(attempt.score) if attempt.score is not None else None,
        "max_score": float(attempt.max_score) if attempt.max_score is not None else None,
        "percent": float(attempt.percent) if attempt.percent is not None else None,
        "items": items,
    }


def compare_attempts(
    user_id: uuid.UUID,
    *,
    attempt_ids: list[uuid.UUID] | None = None,
    paper_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    """
    Compares multiple attempts of a paper or specific attempt IDs.
    """
    qs = Attempt.objects.filter(user_id=user_id, phase=Attempt.Phase.DONE).select_related("paper")
    if attempt_ids:
        qs = qs.filter(id__in=attempt_ids)
    elif paper_id:
        qs = qs.filter(paper_id=paper_id)

    qs = qs.order_by("created_at")

    return [
        {
            "id": str(a.id),
            "attempt_no": a.attempt_no,
            "run_mode": a.run_mode,
            "score": float(a.score) if a.score is not None else None,
            "max_score": float(a.max_score) if a.max_score is not None else None,
            "percent": float(a.percent) if a.percent is not None else None,
            "time_used_seconds": a.time_used_seconds,
            "completed_at": a.completed_at.isoformat() if a.completed_at else None,
        }
        for a in qs
    ]


def percentile_for(user_id: uuid.UUID, attempt_id: uuid.UUID) -> dict[str, Any]:
    """
    Returns percentile or quartile band for an eligible attempt.
    """
    attempt = Attempt.objects.filter(id=attempt_id, user_id=user_id).select_related("paper_version").first()
    if not attempt:
        return {"status": "unavailable", "reason": "not_found"}

    if not attempt.percentile_eligible:
        return {
            "status": "unavailable",
            "reason": "not_eligible",
            "message": "Only clean first attempts with anonymous consent qualify for percentile.",
        }

    cohort = CohortStat.objects.filter(paper_version=attempt.paper_version).first()
    if not cohort or cohort.n < 30:
        return {
            "status": "unavailable",
            "reason": "not_enough_students",
            "message": "Cohort has fewer than 30 attempts so far.",
            "n": cohort.n if cohort else 0,
        }

    # Fetch all eligible scores for this version
    scores = list(
        Attempt.objects.filter(
            paper_version=attempt.paper_version,
            percentile_eligible=True,
            percent__isnull=False,
        ).values_list("percent", flat=True)
    )
    student_score = float(attempt.percent or 0)
    return percentile.get_percentile_view(student_score, len(scores), [float(s) for s in scores])


def list_series(level_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    qs = Series.objects.filter(status=Series.Status.LIVE)
    if level_id:
        qs = qs.filter(level_id=level_id)
    return [
        {
            "id": str(s.id),
            "title": s.title,
            "slug": s.slug,
            "kind": s.kind,
            "series_no": s.series_no,
            "issuer": s.issuer,
            "release_schedule": s.release_schedule,
        }
        for s in qs
    ]


def get_series(slug_or_id: str) -> dict[str, Any] | None:
    try:
        s_uuid = uuid.UUID(slug_or_id)
        s = Series.objects.filter(id=s_uuid).first()
    except ValueError:
        s = Series.objects.filter(slug=slug_or_id).first()

    if not s:
        return None

    papers = list_papers(None, {"series_slug": s.slug})
    return {
        "id": str(s.id),
        "title": s.title,
        "slug": s.slug,
        "kind": s.kind,
        "issuer": s.issuer,
        "release_schedule": s.release_schedule,
        "papers": papers,
    }


def list_formats(level_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    qs = ExamFormat.objects.filter(status=ExamFormat.Status.ACTIVE)
    if level_id:
        qs = qs.filter(level_id=level_id)
    return [
        {
            "id": str(f.id),
            "name": f.name,
            "subject_key": f.subject_key,
            "total_marks": float(f.total_marks),
            "duration_seconds": f.duration_seconds,
            "reading_seconds": f.reading_seconds,
            "sections_spec": f.sections_spec,
            "verified": f.verified,
        }
        for f in qs
    ]
