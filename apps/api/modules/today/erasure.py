"""Account export and delete for Today (FR-F13-45): plans, tasks, evidence and settings. Registered with `core.registry` in `apps.py`."""

from __future__ import annotations

from .models import DayPlan, Task, TaskEvidence, TodaySettings


def delete_all_for_user(user_id) -> dict:
    """Removes every `today_*` row of the student. Idempotent. Tasks and evidence go with their plans (cascade); counts are reported."""
    evidence = TaskEvidence.objects.filter(user_id=user_id).delete()[0]
    tasks = Task.objects.filter(user_id=user_id).delete()[0]
    plans = DayPlan.objects.filter(user_id=user_id).delete()[0]
    settings = TodaySettings.objects.filter(pk=user_id).delete()[0]
    return {"evidence": evidence, "tasks": tasks, "plans": plans, "settings": settings}


def export_for_user(user_id) -> dict:
    """Everything Today holds for the student, JSON-serialisable. Titles are the student's own data, so they are included here."""
    plans = list(DayPlan.objects.filter(user_id=user_id).order_by("local_date"))
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
        "plans": [
            {
                "date": p.local_date.isoformat(),
                "status": p.status,
                "phase": p.phase,
                "budget_minutes": p.budget_minutes,
                "planned": p.planned_count,
                "done": p.done_count,
                "skipped": p.skipped_count,
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
