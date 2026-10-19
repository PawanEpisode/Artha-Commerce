"""
Read-only selectors for student progression, level transition, articleship, and vault (F-18).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from django.utils import timezone

from modules.coverage import selectors as coverage_selectors
from modules.coverage.models import ChapterProgress, Enrollment
from modules.notes.models import Document, Note
from modules.syllabus.models import Level, Subject

from .models import ArticleshipProfile, ExemptionLedger, LevelTransition


def get_articleship_profile(user_id: UUID | str) -> ArticleshipProfile | None:
    return ArticleshipProfile.objects.filter(user_id=user_id).first()


def articleship_dict(profile: ArticleshipProfile | None) -> dict[str, Any]:
    if not profile:
        return {
            "is_active": False,
            "firm_name": "",
            "registration_number": "",
            "training_start_date": None,
            "expected_completion_date": None,
            "study_mode": ArticleshipProfile.StudyMode.ACTIVE_STUDY,
            "weekday_minutes": 120,
            "weekend_minutes": 360,
            "exam_leave_start_date": None,
            "target_groups": [],
        }
    return {
        "id": str(profile.id),
        "is_active": profile.is_active,
        "firm_name": profile.firm_name,
        "registration_number": profile.registration_number,
        "training_start_date": profile.training_start_date.isoformat() if profile.training_start_date else None,
        "expected_completion_date": (
            profile.expected_completion_date.isoformat() if profile.expected_completion_date else None
        ),
        "study_mode": profile.study_mode,
        "weekday_minutes": profile.weekday_minutes,
        "weekend_minutes": profile.weekend_minutes,
        "exam_leave_start_date": (
            profile.exam_leave_start_date.isoformat() if profile.exam_leave_start_date else None
        ),
        "target_groups": profile.target_groups or [],
    }


def get_exemptions(user_id: UUID | str, only_active: bool = True) -> list[dict[str, Any]]:
    qs = ExemptionLedger.objects.filter(user_id=user_id)
    if only_active:
        qs = qs.filter(is_exhausted=False)
    qs = qs.order_by("-created_at")

    # Fetch subject names matching subject keys
    subject_keys = list(qs.values_list("subject_key", flat=True))
    subject_map = {
        s.key: s.name for s in Subject.objects.filter(key__in=subject_keys)
    }

    result = []
    for item in qs:
        result.append(
            {
                "id": str(item.id),
                "subject_key": item.subject_key,
                "subject_name": subject_map.get(item.subject_key, item.subject_key.replace("-", " ").title()),
                "marks_obtained": item.marks_obtained,
                "granted_term_code": item.granted_term_code,
                "valid_until_term_code": item.valid_until_term_code,
                "is_permanent": item.is_permanent,
                "is_exhausted": item.is_exhausted,
                "is_valid": not item.is_exhausted,
            }
        )
    return result


def get_transition_history(user_id: UUID | str) -> list[dict[str, Any]]:
    transitions = (
        LevelTransition.objects.filter(user_id=user_id)
        .select_related("from_enrollment__scheme__level__course", "to_enrollment__scheme__level__course")
        .prefetch_related("paper_results")
        .order_by("-created_at")
    )
    now = timezone.now()
    rollback_cutoff = now - timedelta(hours=48)

    history = []
    for t in transitions:
        can_rollback = t.status == LevelTransition.Status.APPLIED and t.created_at >= rollback_cutoff
        history.append(
            {
                "id": str(t.id),
                "transition_type": t.transition_type,
                "trigger": t.trigger,
                "status": t.status,
                "effective_date": t.effective_date.isoformat(),
                "created_at": t.created_at.isoformat(),
                "can_rollback": can_rollback,
                "from_level": (
                    {
                        "course_code": t.from_enrollment.scheme.level.course.code,
                        "level_code": t.from_enrollment.scheme.level.code,
                        "level_name": t.from_enrollment.scheme.level.name,
                    }
                    if t.from_enrollment and t.from_enrollment.scheme
                    else None
                ),
                "to_level": (
                    {
                        "course_code": t.to_enrollment.scheme.level.course.code,
                        "level_code": t.to_enrollment.scheme.level.code,
                        "level_name": t.to_enrollment.scheme.level.name,
                    }
                    if t.to_enrollment and t.to_enrollment.scheme
                    else None
                ),
                "paper_results": [
                    {
                        "subject_key": pr.subject_key,
                        "status": pr.status,
                        "marks_obtained": pr.marks_obtained,
                        "is_carry_forward": pr.is_carry_forward,
                    }
                    for pr in t.paper_results.all()
                ],
                "metadata": t.metadata or {},
            }
        )
    return history


def get_available_transitions(active_enrollment: Enrollment | None) -> list[dict[str, Any]]:
    if not active_enrollment or not active_enrollment.level:
        return []

    course = active_enrollment.level.course
    levels = list(Level.objects.filter(course=course, is_active=True).order_by("sort_order"))
    current_idx = next((i for i, lvl in enumerate(levels) if lvl.id == active_enrollment.level_id), -1)

    transitions = []

    # If there is a next level in this course
    if current_idx >= 0 and current_idx + 1 < len(levels):
        next_level = levels[current_idx + 1]
        transitions.append(
            {
                "type": "full_level_pass",
                "target_level_code": next_level.code,
                "target_level_name": next_level.name,
                "label": f"Promote to {course.name} {next_level.name}",
                "description": f"Graduate to {next_level.name} and archive {active_enrollment.level.name} syllabus to Vault.",
            }
        )

    # Check if current scheme has groups (e.g. Group 1, Group 2)
    scheme = active_enrollment.scheme
    groups = list(scheme.groups.all().order_by("sort_order")) if scheme else []
    if groups:
        transitions.append(
            {
                "type": "group_clearance",
                "label": "Group Clearance (Single Group Focus)",
                "description": "Mark one group as cleared and focus 100% of study bandwidth on remaining papers.",
            }
        )

    transitions.append(
        {
            "type": "exemption_update",
            "label": "Paper Exemptions (60+ Marks)",
            "description": "Carry forward paper exemptions and recalibrate remaining syllabus targets.",
        }
    )
    transitions.append(
        {
            "type": "repeat_attempt",
            "label": "Re-attempt / Syllabus Refresh",
            "description": "Keep current level, reset chapter targets, and review diagnostic weak areas.",
        }
    )

    return transitions


def get_current_groups_and_papers(active_enrollment: Enrollment | None) -> list[dict[str, Any]]:
    if not active_enrollment or not active_enrollment.scheme:
        return []

    scheme = active_enrollment.scheme
    groups = list(scheme.groups.all().order_by("sort_order"))
    subjects = list(
        scheme.subjects.filter(is_active=True)
        .select_related("group")
        .order_by("sort_order", "paper_number")
    )

    user_id = active_enrollment.user_id
    # A subject is considered excluded if all its active chapters are excluded
    progress_by_chapter = {
        cp.chapter_id: cp.is_excluded
        for cp in ChapterProgress.objects.filter(enrollment=active_enrollment, user_id=user_id)
    }

    group_data = []
    if groups:
        for g in groups:
            group_subjects = [s for s in subjects if s.group_id == g.id]
            group_data.append(
                {
                    "key": g.key,
                    "name": g.name,
                    "papers": [
                        {
                            "id": str(s.id),
                            "key": s.key,
                            "paper_number": s.paper_number,
                            "name": s.name,
                            "total_marks": s.total_marks or 100,
                            "is_excluded": all(
                                progress_by_chapter.get(ch.id, False) for ch in s.chapters.filter(is_active=True)
                            )
                            if s.chapters.exists()
                            else False,
                        }
                        for s in group_subjects
                    ],
                }
            )
    else:
        group_data.append(
            {
                "key": "all_papers",
                "name": "Papers",
                "papers": [
                    {
                        "id": str(s.id),
                        "key": s.key,
                        "paper_number": s.paper_number,
                        "name": s.name,
                        "total_marks": s.total_marks or 100,
                        "is_excluded": all(
                            progress_by_chapter.get(ch.id, False) for ch in s.chapters.filter(is_active=True)
                        )
                        if s.chapters.exists()
                        else False,
                    }
                    for s in subjects
                ],
            }
        )

    return group_data


def get_result_prompt_state(user_id: UUID | str, active_enrollment: Enrollment | None) -> dict[str, Any]:
    if not active_enrollment:
        return {"should_prompt": False, "term_name": "", "level_name": ""}

    exam_date = coverage_selectors.exam_date_of(active_enrollment)
    now = timezone.now().date()

    # Prompt if exam date has passed and student hasn't completed a transition in the last 60 days
    has_recent_transition = LevelTransition.objects.filter(
        user_id=user_id,
        created_at__gte=timezone.now() - timedelta(days=60),
        status=LevelTransition.Status.APPLIED,
    ).exists()

    should_prompt = bool(exam_date and exam_date <= now and not has_recent_transition)
    term_name = active_enrollment.target_term.name if active_enrollment.target_term else "Recent"
    level_name = active_enrollment.level.name if active_enrollment.level else "Intermediate"

    return {
        "should_prompt": should_prompt,
        "term_name": term_name,
        "level_name": level_name,
        "exam_date": exam_date.isoformat() if exam_date else None,
    }


def get_vault_enrollments(user_id: UUID | str) -> list[dict[str, Any]]:
    """
    Returns archived enrollments for the student, providing read-only access to past level notes, docs, and syllabus.
    """
    archived_enrollments = (
        Enrollment.objects.filter(user_id=user_id, status=Enrollment.Status.ARCHIVED)
        .select_related("scheme__level__course", "target_term")
        .order_by("-created_at")
    )

    vault_list = []
    for enr in archived_enrollments:
        scheme = enr.scheme
        level = scheme.level if scheme else enr.level
        course = level.course if level else None

        # Count notes and documents created under this level
        notes_count = Note.objects.filter(user_id=user_id, level=level).count()
        docs_count = Document.objects.filter(user_id=user_id, level=level).count()

        subjects_summary = []
        if scheme:
            for s in scheme.subjects.filter(is_active=True).order_by("sort_order", "paper_number"):
                subjects_summary.append(
                    {
                        "key": s.key,
                        "paper_number": s.paper_number,
                        "name": s.name,
                    }
                )

        vault_list.append(
            {
                "enrollment_id": str(enr.id),
                "course_code": course.code if course else "",
                "course_name": course.name if course else "",
                "level_code": level.code if level else "",
                "level_name": level.name if level else "",
                "scheme_name": scheme.name if scheme else "",
                "term_name": enr.target_term.name if enr.target_term else "",
                "exam_date": enr.exam_date.isoformat() if enr.exam_date else None,
                "notes_count": notes_count,
                "docs_count": docs_count,
                "subjects": subjects_summary,
            }
        )

    return vault_list


def get_progression_status(user_id: UUID | str) -> dict[str, Any]:
    active_enrollment = coverage_selectors.get_active_enrollment(user_id)
    articleship = get_articleship_profile(user_id)
    exemptions = get_exemptions(user_id)
    available_transitions = get_available_transitions(active_enrollment)
    current_groups = get_current_groups_and_papers(active_enrollment)
    prompt_state = get_result_prompt_state(user_id, active_enrollment)

    active_dict = None
    if active_enrollment:
        scheme = active_enrollment.scheme
        level = scheme.level if scheme else active_enrollment.level
        course = level.course if level else None
        active_dict = {
            "id": str(active_enrollment.id),
            "course_code": course.code if course else "",
            "course_name": course.name if course else "",
            "level_code": level.code if level else "",
            "level_name": level.name if level else "",
            "scheme_id": str(scheme.id) if scheme else None,
            "scheme_name": scheme.name if scheme else "",
            "term_code": active_enrollment.target_term.code if active_enrollment.target_term else None,
            "term_name": active_enrollment.target_term.name if active_enrollment.target_term else None,
            "exam_date": active_enrollment.exam_date.isoformat() if active_enrollment.exam_date else None,
            "daily_minutes": active_enrollment.planned_minutes,
        }

    return {
        "active_enrollment": active_dict,
        "articleship": articleship_dict(articleship),
        "exemptions": exemptions,
        "available_transitions": available_transitions,
        "current_groups": current_groups,
        "result_prompt": prompt_state,
    }


def export_all(user_id: UUID | str) -> dict[str, Any]:
    """
    DPDP export handler for the student's progression data.
    """
    articleship = get_articleship_profile(user_id)
    exemptions = get_exemptions(user_id, only_active=False)
    history = get_transition_history(user_id)
    vault = get_vault_enrollments(user_id)

    return {
        "articleship": articleship_dict(articleship),
        "exemptions": exemptions,
        "transition_history": history,
        "vault_archived_enrollments": vault,
    }
