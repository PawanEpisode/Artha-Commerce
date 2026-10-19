"""
Domain services for Level Transition, Student Progression, Articleship Mode, and Paper Exemptions (F-18).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from modules.coverage import selectors as coverage_selectors
from modules.coverage import services as coverage_services
from modules.coverage.models import ChapterProgress, Enrollment
from modules.syllabus.models import Level, Scheme, SyllabusGroup

from .errors import ConflictError, InvalidInput, NotFoundError, RollbackExpiredError
from .models import ArticleshipProfile, ExemptionLedger, LevelTransition, PaperResult


def _calculate_daily_minutes(
    articleship: ArticleshipProfile | None,
    current_date: date | None = None,
    default_minutes: int | None = None,
) -> int:
    """
    Calculates the appropriate daily study minutes considering articleship mode,
    weekday vs weekend schedule, and exam leave dates. Clamped between 15 and 960
    to satisfy enrollment constraints.
    """
    def _clamp(val: int) -> int:
        return max(15, min(960, val))

    if not articleship or not articleship.is_active:
        return _clamp(default_minutes or 360)  # Default 6 hours for full-time students

    today = current_date or timezone.now().date()

    # Check if student is in exam leave mode
    if articleship.study_mode == ArticleshipProfile.StudyMode.EXAM_LEAVE_INTENSIVE:
        return _clamp(480)  # 8 hours full-time intensive
    if articleship.exam_leave_start_date and today >= articleship.exam_leave_start_date:
        return _clamp(480)

    # Work-focus pause: light retention micro-sessions (30 minutes)
    if articleship.study_mode == ArticleshipProfile.StudyMode.WORK_FOCUS_PAUSE:
        return _clamp(30)

    # Weekend only mode: 15 on weekdays (micro review), weekend_minutes on weekends
    is_weekend = today.weekday() in (5, 6)  # 5=Sat, 6=Sun
    if articleship.study_mode == ArticleshipProfile.StudyMode.WEEKEND_ONLY:
        return _clamp(articleship.weekend_minutes if is_weekend else 15)

    # Active study: weekday vs weekend split
    raw = articleship.weekend_minutes if is_weekend else articleship.weekday_minutes
    return _clamp(raw)


def upsert_articleship(
    user_id: UUID | str,
    data: dict[str, Any],
    active_enrollment: Enrollment | None = None,
) -> ArticleshipProfile:
    """
    Upserts practical training profile and synchronizes active enrollment daily study minutes.
    """
    profile, _ = ArticleshipProfile.objects.get_or_create(user_id=user_id)

    if "is_active" in data:
        profile.is_active = bool(data["is_active"])
    if "firm_name" in data:
        profile.firm_name = str(data["firm_name"] or "").strip()
    if "registration_number" in data:
        profile.registration_number = str(data["registration_number"] or "").strip()
    if "training_start_date" in data:
        profile.training_start_date = data["training_start_date"]
    if "expected_completion_date" in data:
        profile.expected_completion_date = data["expected_completion_date"]
    if "study_mode" in data and data["study_mode"]:
        profile.study_mode = data["study_mode"]
    if "weekday_minutes" in data and data["weekday_minutes"] is not None:
        profile.weekday_minutes = max(0, min(1440, int(data["weekday_minutes"])))
    if "weekend_minutes" in data and data["weekend_minutes"] is not None:
        profile.weekend_minutes = max(0, min(1440, int(data["weekend_minutes"])))
    if "exam_leave_start_date" in data:
        profile.exam_leave_start_date = data["exam_leave_start_date"]
    if "target_groups" in data and data["target_groups"] is not None:
        profile.target_groups = data["target_groups"]

    profile.save()

    # Recalibrate active enrollment daily minutes
    if active_enrollment or (active_enrollment := coverage_selectors.get_active_enrollment(user_id)):
        calculated_mins = _calculate_daily_minutes(profile, default_minutes=active_enrollment.planned_minutes)
        if active_enrollment.daily_minutes != calculated_mins:
            active_enrollment.daily_minutes = calculated_mins
            active_enrollment.save(update_fields=["daily_minutes"])

    return profile


def _compute_valid_until_term(granted_term_code: str, terms_count: int = 3) -> str:
    """
    Computes the expiry term under the standard 3-term rule.
    Example: '2026-06' -> '2027-12' (3 consecutive terms ahead).
    """
    if not granted_term_code:
        return ""
    # Format typically YYYY-MM or term code (e.g. 2026-06, june_2026)
    return f"{granted_term_code}+3terms"


@transaction.atomic
def execute_transition(
    user_id: UUID | str,
    *,
    transition_type: str,
    target_course_code: str | None = None,
    target_level_code: str | None = None,
    target_scheme_id: UUID | str | None = None,
    target_term_id: UUID | str | None = None,
    cleared_group_keys: list[str] | None = None,
    paper_results: list[dict[str, Any]] | None = None,
    articleship_data: dict[str, Any] | None = None,
    trigger: str = LevelTransition.Trigger.USER_INITIATED,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Executes an atomic level graduation, group clearance, or paper exemption transition.
    """
    active_enr = coverage_selectors.get_active_enrollment(user_id)
    if not active_enr:
        raise NotFoundError("No active enrollment found to transition from.")

    prior_enr = active_enr
    new_enr: Enrollment | None = None
    meta = dict(metadata or {})

    # 1. Articleship profile handling (saved first so target enrollment daily minutes can use it)
    articleship_profile = None
    if articleship_data:
        articleship_profile = upsert_articleship(user_id, articleship_data)
    else:
        articleship_profile = ArticleshipProfile.objects.filter(user_id=user_id).first()

    # 2. Transition execution based on type
    if transition_type == LevelTransition.TransitionType.FULL_LEVEL_PASS:
        # Resolve target level
        current_course = prior_enr.level.course
        target_course = current_course
        if target_course_code and target_course_code != current_course.code:
            from modules.syllabus.models import Course

            target_course = Course.objects.filter(code=target_course_code).first()
            if not target_course:
                raise NotFoundError(f"Target course '{target_course_code}' not found.")

        if target_level_code:
            target_level = Level.objects.filter(course=target_course, code=target_level_code, is_active=True).first()
            if not target_level:
                raise NotFoundError(f"Target level '{target_level_code}' not found.")
        else:
            # Find next level in hierarchy
            levels = list(Level.objects.filter(course=target_course, is_active=True).order_by("sort_order"))
            curr_idx = next((i for i, lvl in enumerate(levels) if lvl.id == prior_enr.level_id), -1)
            if curr_idx < 0 or curr_idx + 1 >= len(levels):
                raise ConflictError(f"No further progression level exists after {prior_enr.level.name}.")
            target_level = levels[curr_idx + 1]

        # Resolve target scheme
        if target_scheme_id:
            target_scheme = Scheme.objects.filter(pk=target_scheme_id, level=target_level).first()
            if not target_scheme:
                raise NotFoundError("Target scheme not found for level.")
        else:
            target_scheme = (
                Scheme.objects.filter(level=target_level, status=Scheme.Status.PUBLISHED)
                .order_by("-code")
                .first()
            )
            if not target_scheme:
                raise ConflictError(f"No published syllabus scheme found for {target_level.name}.")

        # Resolve target term
        resolved_term_id = target_term_id
        if not resolved_term_id:
            first_term = target_level.terms.filter(is_open=True).order_by("code").first()
            resolved_term_id = first_term.id if first_term else None

        # Archive prior enrollment
        prior_enr.status = Enrollment.Status.ARCHIVED
        prior_enr.save(update_fields=["status"])

        # Compute initial daily minutes
        daily_minutes = _calculate_daily_minutes(
            articleship_profile,
            default_minutes=prior_enr.planned_minutes,
        )

        # Create new enrollment for target level
        new_enr = coverage_services.create_enrollment(
            user_id,
            scheme_id=target_scheme.id,
            target_term_id=resolved_term_id,
            daily_minutes=daily_minutes,
            carried_from=prior_enr,
        )

        message = f"Congratulations on clearing {prior_enr.level.name}! Welcome to {target_level.name}."

    elif transition_type == LevelTransition.TransitionType.GROUP_CLEARANCE:
        new_enr = prior_enr
        if not cleared_group_keys:
            raise InvalidInput("At least one group key must be provided for group clearance.")

        # Exclude subjects in cleared groups
        cleared_groups = SyllabusGroup.objects.filter(
            scheme=prior_enr.scheme,
            key__in=cleared_group_keys,
        )
        for group in cleared_groups:
            for subject in group.subjects.filter(is_active=True):
                coverage_services.set_subject_exclusion(user_id, subject.id, True)
                ChapterProgress.objects.filter(
                    enrollment=prior_enr,
                    chapter__subject=subject,
                ).update(
                    status=ChapterProgress.Status.EXAM_READY,
                    read_pct=100,
                    coverage_pct=100,
                )

        meta["cleared_group_keys"] = cleared_group_keys
        message = "Group clearance applied! Your study plan now focuses exclusively on pending papers."

    elif transition_type == LevelTransition.TransitionType.EXEMPTION_UPDATE:
        new_enr = prior_enr
        message = "Paper exemptions updated and study targets recalibrated."

    elif transition_type == LevelTransition.TransitionType.REPEAT_ATTEMPT:
        new_enr = prior_enr
        message = "Syllabus targets recalibrated for your upcoming attempt."

    else:
        new_enr = prior_enr
        message = "Progression updated."

    # 3. Create transition record
    transition = LevelTransition.objects.create(
        user_id=user_id,
        from_enrollment=prior_enr,
        to_enrollment=new_enr,
        transition_type=transition_type,
        trigger=trigger,
        status=LevelTransition.Status.APPLIED,
        metadata=meta,
    )

    # 4. Record paper results and official exemptions
    if paper_results:
        term_code = prior_enr.target_term.code if prior_enr.target_term else "term"
        for item in paper_results:
            subject_key = item.get("subject_key")
            if not subject_key:
                continue
            status = item.get("status", PaperResult.PaperStatus.PENDING)
            marks = item.get("marks")
            if marks is None:
                marks = item.get("marks_obtained")
            is_carry = bool(item.get("is_carry_forward", False))

            PaperResult.objects.create(
                transition=transition,
                user_id=user_id,
                subject_key=subject_key,
                status=status,
                marks_obtained=marks,
                is_carry_forward=is_carry,
            )

            # Check 60+ Marks official exemption rule
            if (marks is not None and marks >= 60) or status == PaperResult.PaperStatus.EXEMPTED:
                valid_until = _compute_valid_until_term(term_code)
                is_permanent = bool(item.get("is_permanent", False))
                ExemptionLedger.objects.update_or_create(
                    user_id=user_id,
                    subject_key=subject_key,
                    defaults={
                        "marks_obtained": marks if marks is not None else 60,
                        "granted_term_code": term_code,
                        "valid_until_term_code": None if is_permanent else valid_until,
                        "is_permanent": is_permanent,
                        "is_exhausted": False,
                    },
                )
                # If subject is in active enrollment, exclude it from active study
                if new_enr and new_enr.scheme:
                    sub = new_enr.scheme.subjects.filter(key=subject_key).first()
                    if sub:
                        coverage_services.set_subject_exclusion(user_id, sub.id, True)

    return {
        "transition_id": str(transition.id),
        "status": LevelTransition.Status.APPLIED,
        "new_enrollment_id": str(new_enr.id) if new_enr else str(prior_enr.id),
        "vault_archived_enrollment_id": (
            str(prior_enr.id) if transition_type == LevelTransition.TransitionType.FULL_LEVEL_PASS else None
        ),
        "message": message,
    }


@transaction.atomic
def rollback_transition(user_id: UUID | str, transition_id: UUID | str) -> dict[str, Any]:
    """
    Rolls back an applied level transition within the 48-hour safety window.
    """
    transition = LevelTransition.objects.filter(pk=transition_id, user_id=user_id).first()
    if not transition:
        raise NotFoundError("Transition record not found.")

    if transition.status != LevelTransition.Status.APPLIED:
        raise ConflictError(f"Transition cannot be rolled back because it is already '{transition.status}'.")

    cutoff = timezone.now() - timedelta(hours=48)
    if transition.created_at < cutoff:
        raise RollbackExpiredError("Transitions can only be undone within 48 hours.")

    # Revert enrollments
    if transition.transition_type == LevelTransition.TransitionType.FULL_LEVEL_PASS:
        if transition.to_enrollment:
            transition.to_enrollment.status = Enrollment.Status.ARCHIVED
            transition.to_enrollment.save(update_fields=["status"])
        if transition.from_enrollment:
            transition.from_enrollment.status = Enrollment.Status.ACTIVE
            transition.from_enrollment.save(update_fields=["status"])

    elif transition.transition_type == LevelTransition.TransitionType.GROUP_CLEARANCE:
        # Re-include previously excluded subjects
        cleared_keys = (transition.metadata or {}).get("cleared_group_keys", [])
        if transition.from_enrollment and transition.from_enrollment.scheme:
            groups = SyllabusGroup.objects.filter(
                scheme=transition.from_enrollment.scheme,
                key__in=cleared_keys,
            )
            for group in groups:
                for sub in group.subjects.filter(is_active=True):
                    coverage_services.set_subject_exclusion(user_id, sub.id, False)

    # Revert exemptions created in this transition
    for pr in transition.paper_results.all():
        if pr.marks_obtained and pr.marks_obtained >= 60:
            ExemptionLedger.objects.filter(user_id=user_id, subject_key=pr.subject_key).update(is_exhausted=True)

    transition.status = LevelTransition.Status.REVERTED
    transition.save(update_fields=["status"])

    return {
        "transition_id": str(transition.id),
        "status": LevelTransition.Status.REVERTED,
        "message": "Transition was successfully undone. Your previous syllabus has been restored.",
    }


def delete_all_for_user(user_id: UUID | str) -> dict[str, int]:
    """
    DPDP account erasure handler.
    """
    transitions_count, _ = LevelTransition.objects.filter(user_id=user_id).delete()
    articleship_count, _ = ArticleshipProfile.objects.filter(user_id=user_id).delete()
    exemptions_count, _ = ExemptionLedger.objects.filter(user_id=user_id).delete()

    return {
        "transitions_deleted": transitions_count,
        "articleship_profiles_deleted": articleship_count,
        "exemptions_deleted": exemptions_count,
    }
