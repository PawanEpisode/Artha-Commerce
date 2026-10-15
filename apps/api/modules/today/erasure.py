"""Account export and delete for Today (FR-F13-45): plans, tasks, evidence and settings. Registered with `core.registry` in `apps.py`."""

from __future__ import annotations

from .models import DayFeedback, DayPlan, Milestone, ReplanEvent, StudyPlan, Task, TaskEvidence, TodaySettings


def delete_all_for_user(user_id) -> dict:
    """Removes every `today_*` row of the student, the planner's included. Idempotent. Tasks and evidence go with their plans (cascade); counts are reported."""
    evidence = TaskEvidence.objects.filter(user_id=user_id).delete()[0]
    tasks = Task.objects.filter(user_id=user_id).delete()[0]
    feedback = DayFeedback.objects.filter(user_id=user_id).delete()[0]
    plans = DayPlan.objects.filter(user_id=user_id).delete()[0]
    settings = TodaySettings.objects.filter(pk=user_id).delete()[0]
    replan_events = ReplanEvent.objects.filter(user_id=user_id).delete()[0]
    milestones = Milestone.objects.filter(user_id=user_id).delete()[0]
    study_plans = StudyPlan.objects.filter(user_id=user_id).delete()[0]
    return {
        "evidence": evidence,
        "tasks": tasks,
        "plans": plans,
        "settings": settings,
        "replan_events": replan_events,
        "milestones": milestones,
        "study_plans": study_plans,
        "feedback": feedback,
    }


def export_for_user(user_id) -> dict:
    """Everything Today holds for the student, JSON-serialisable. Titles are the student's own data, so they are included here."""
    plans = list(DayPlan.objects.filter(user_id=user_id).order_by("local_date"))
    feedback_of = dict(DayFeedback.objects.filter(user_id=user_id).values_list("plan_id", "rating"))
    tasks = Task.objects.filter(user_id=user_id, deleted_at__isnull=True).order_by("local_date", "position")
    by_plan: dict = {}
    for t in tasks:
        by_plan.setdefault(t.plan_id, []).append(
            {
                "id": str(t.id),
                "origin": t.origin,
                "kind": t.kind,
                "title": t.title,
                "reason": t.reason,
                "state": t.state,
                "est_minutes": t.est_minutes,
                "completed_via": t.completed_via,
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "skip_reason": t.skip_reason,
                "carry_count": t.carry_count,
            }
        )
    settings = TodaySettings.objects.filter(pk=user_id).first()
    return {
        "study_plans": [
            _export_study_plan(p) for p in StudyPlan.objects.filter(user_id=user_id).order_by("created_at")
        ],
        "plans": [
            {
                "date": p.local_date.isoformat(),
                "status": p.status,
                "phase": p.phase,
                "budget_minutes": p.budget_minutes,
                "planned": p.planned_count,
                "done": p.done_count,
                "skipped": p.skipped_count,
                "feedback": feedback_of.get(p.id),
                "tasks": by_plan.get(p.id, []),
            }
            for p in plans
        ],
        "settings": None
        if settings is None
        else {
            "minutes_per_day": settings.minutes_per_day,
            "focus_papers": settings.focus_papers,
            "disabled_kinds": list(settings.disabled_kinds),
            "show_tomorrow": settings.show_tomorrow,
            "celebrate": settings.celebrate,
            "lite_mode": settings.lite_mode,
        },
    }


def _export_study_plan(plan: StudyPlan) -> dict:
    return {
        "status": plan.status,
        "exam_date": plan.exam_date.isoformat(),
        "daily_minutes": plan.daily_minutes,
        "health": plan.health,
        "capacity_minutes": plan.capacity_minutes,
        "remaining_minutes": plan.remaining_minutes,
        "shortfall_minutes": plan.shortfall_minutes,
        "reading_deadline": plan.reading_deadline.isoformat() if plan.reading_deadline else None,
        "milestones": [
            {
                "kind": m.kind,
                "subject_key": m.subject_key,
                "target_date": m.target_date.isoformat(),
                "original_target_date": m.original_target_date.isoformat(),
                "status": m.status,
            }
            for m in plan.milestones.order_by("sort_order", "target_date")
        ],
        "replans": [
            {
                "trigger": e.trigger,
                "health_before": e.health_before,
                "health_after": e.health_after,
                "moved_count": e.moved_count,
                "option_chosen": e.option_chosen,
                "at": e.created_at.isoformat(),
            }
            for e in plan.replan_events.order_by("created_at")
        ],
    }
