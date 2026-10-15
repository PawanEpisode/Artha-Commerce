"""
Request parsing and response shapes for /api/v1/today/ (PRD section 9, `docs/F-13-API-CONTRACT.md`). Plain functions build the
plan payload from rows, so the same code answers `open/` and `plan/` and the contract test can pin every key.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime

from rest_framework import serializers

from . import registry, selectors
from .adapters import tracking as tracking_adapter
from .domain import constants as c
from .domain.week import day_closing
from .models import DayPlan, Task, TodaySettings
from .runner import PARTIAL_STATUSES

PLAN_VERSION = 1
OPEN_SOURCES = ("nav", "reminder", "redirect")


# ---- requests ---------------------------------------------------------------------------------------------------------------


class OpenSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=False)
    date = serializers.DateField(required=False)
    source = serializers.ChoiceField(choices=OPEN_SOURCES, required=False, default="nav")


class DateQuerySerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    lite = serializers.BooleanField(required=False, default=False)


class PreviewQuerySerializer(serializers.Serializer):
    date = serializers.DateField()


class HistoryQuerySerializer(serializers.Serializer):
    # `from` is a Python keyword: the query parameter is read as `from` and exposed here as `first`
    first = serializers.DateField(required=False)
    to = serializers.DateField(required=False)

    def to_internal_value(self, data):
        data = {"first": data.get("from"), "to": data.get("to")}
        return super().to_internal_value({k: v for k, v in data.items() if v not in (None, "")})


class SettingsSerializer(serializers.Serializer):
    minutes_per_day = serializers.IntegerField(
        required=False, allow_null=True, min_value=c.SETTING_MINUTES_MIN, max_value=c.SETTING_MINUTES_MAX
    )
    focus_papers = serializers.IntegerField(
        required=False, allow_null=True, min_value=c.FOCUS_PAPERS_MIN, max_value=c.FOCUS_PAPERS_SETTING_MAX
    )
    disabled_kinds = serializers.ListField(
        child=serializers.CharField(max_length=40), required=False, max_length=c.DISABLED_KINDS_MAX
    )
    show_tomorrow = serializers.BooleanField(required=False)
    celebrate = serializers.BooleanField(required=False)
    lite_mode = serializers.ChoiceField(choices=c.LITE_MODES, required=False)

    def validate_disabled_kinds(self, value):
        known = {k.name for spec in registry.providers() for k in spec.kinds}
        unknown = sorted(set(value) - known)
        if unknown:
            raise serializers.ValidationError(f"Unknown task kinds: {', '.join(unknown)}.")
        return sorted(set(value))


REGENERATE_REASONS = ("manual", "exam_date", "settings", "provider_recovered")
UNDO_FROM = ("done", "skipped", "deleted")
SKIP_REASONS_PUBLIC = tuple(r for r in c.SKIP_REASONS if r != "swapped")  # `swapped` is the swap endpoint's own reason


class ActionSerializer(serializers.Serializer):
    """Every task action: `client_id` makes a retry harmless, `client_ts` orders writes from different devices."""

    client_id = serializers.UUIDField()
    client_ts = serializers.DateTimeField(required=False)


class CompleteSerializer(ActionSerializer):
    run_manual_action = serializers.BooleanField(required=False, default=False)


class SkipSerializer(ActionSerializer):
    reason = serializers.ChoiceField(choices=SKIP_REASONS_PUBLIC, required=False, allow_null=True)


class SnoozeSerializer(ActionSerializer):
    until = serializers.CharField(max_length=20)

    def validate_until(self, value):
        if value in c.SNOOZE_PRESET_DAYS:
            return value
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise serializers.ValidationError("Use a date (YYYY-MM-DD) or tomorrow, in_3_days, next_week.") from error


class UndoSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    from_state = serializers.ChoiceField(choices=UNDO_FROM)


class DeleteSerializer(serializers.Serializer):
    client_id = serializers.UUIDField(required=False)


class AddTaskSerializer(serializers.Serializer):
    client_id = serializers.UUIDField()
    title = serializers.CharField(max_length=c.TITLE_MAX, trim_whitespace=True)
    date = serializers.DateField(required=False)
    subject_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    chapter_id = serializers.UUIDField(required=False, allow_null=True, default=None)
    est_minutes = serializers.IntegerField(min_value=c.OWN_EST_MIN, max_value=c.OWN_EST_MAX)


class EditTaskSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=c.TITLE_MAX, trim_whitespace=True, required=False)
    date = serializers.DateField(required=False)
    subject_id = serializers.UUIDField(required=False, allow_null=True)
    chapter_id = serializers.UUIDField(required=False, allow_null=True)
    est_minutes = serializers.IntegerField(min_value=c.OWN_EST_MIN, max_value=c.OWN_EST_MAX, required=False)

    def validate(self, attrs):
        if not set(attrs) - {"version"}:
            raise serializers.ValidationError("Send at least one field to change.")
        return attrs


class RegenerateSerializer(serializers.Serializer):
    expected_generation = serializers.IntegerField(min_value=0)
    reason = serializers.ChoiceField(choices=REGENERATE_REASONS, default="manual")
    client_id = serializers.UUIDField()


# ---- responses --------------------------------------------------------------------------------------------------------------


def link_of(task: Task) -> dict:
    return {"path": task.link_path, "search": dict(task.link_search or {})}


def task_dict(task: Task, *, lite: bool = False) -> dict:
    breakdown = task.score_breakdown or {}
    why = {"modifiers": list(breakdown.get("modifiers", []))[:2]}
    if not lite:
        why["signals"] = breakdown.get("signals", {})
    action = task.manual_action
    return {
        "id": str(task.id),
        "origin": task.origin,
        "kind": task.kind,
        "slot": task.slot,
        "title": task.title,
        "reason": task.reason,
        "reason_code": task.reason_code,
        "why": why,
        "est_minutes": task.est_minutes,
        "progress": task.progress_value,
        "target": task.target_value,
        "state": task.state,
        "link": link_of(task),
        "subject_id": str(task.subject_id) if task.subject_id else None,
        "chapter_id": str(task.chapter_id) if task.chapter_id else None,
        "manual_action": {"label": action["label"], "default": action["default"]} if action else None,
        "is_must_do": task.is_must_do,
        "version": task.version,
    }


def _starter(tasks: list[Task]) -> str | None:
    """The "Start here" task: the highest score among open tasks of 10 minutes or less, else the highest overall."""
    open_tasks = [t for t in tasks if t.state in c.OPEN_STATES and t.counts_toward_day]
    short = [t for t in open_tasks if t.est_minutes <= c.STARTER_MAX_MINUTES]
    pool = short or open_tasks
    best = min(pool, key=lambda t: (-t.score, t.position, str(t.id)), default=None)
    return str(best.id) if best else None


def _tiles(tasks: list[Task]) -> list[dict]:
    """One tile per paper in order of first appearance (positions are already the display order), the General pool last."""
    tiles: dict = {}
    for t in tasks:
        key = t.subject_id
        if key not in tiles:
            subject = t.subject
            tiles[key] = {
                "subject_id": str(key) if key else None,
                "subject_key": t.subject_key,
                "name": subject.name if subject else "",
                "tasks": [],
            }
        tiles[key]["tasks"].append(str(t.id))
    ordered = [v for k, v in tiles.items() if k is not None] + ([tiles[None]] if None in tiles else [])
    return ordered


def _backlog(plan: DayPlan, tasks: list[Task]) -> list[dict]:
    out = []
    for provider, status in sorted((plan.provider_status or {}).items()):
        info = status.get("backlog")
        if not info:
            continue
        out.append(
            {
                "kind": provider.split(".", 1)[-1],
                "count": info["count"],
                "scheduled": sum(1 for t in tasks if t.provider == provider and t.state != "skipped"),
                "label": info["label"],
                "link": info["link"],
            }
        )
    return out


def plan_payload(plan: DayPlan, *, user_id, now: datetime, lite: bool = False) -> dict:
    """The plan payload, version 1 (PRD section 9). Reads only."""
    tasks = list(selectors.live_tasks(plan))
    settings = selectors.get_settings(user_id)
    streak, goal = tracking_adapter.streak_and_goal(user_id, plan.local_date)
    closing = day_closing(open_count=plan.open_count, done_count=plan.done_count, skipped_count=plan.skipped_count)
    payload = {
        "version": PLAN_VERSION,
        "date": plan.local_date.isoformat(),
        "tz": plan.tz,
        "server_time": now.isoformat(),
        "state": "ready",
        "phase": plan.phase,
        "days_to_exam": plan.days_to_exam,
        "generation_no": plan.generation_no,
        "partial": plan.partial,
        "failed_providers": sorted(
            name for name, s in (plan.provider_status or {}).items() if s.get("status") in PARTIAL_STATUSES
        ),
        "budget_minutes": plan.budget_minutes,
        "planned_minutes": plan.planned_minutes,
        "counts": {
            "planned": plan.planned_count,
            "done": plan.done_count,
            "open": plan.open_count,
            "skipped": plan.skipped_count,
            "snoozed": plan.snoozed_count,
        },
        "starter_task_id": _starter(tasks),
        "backlog": _backlog(plan, tasks),
        "tiles": _tiles(tasks),
        "tasks": [task_dict(t, lite=lite) for t in tasks],
        "streak": streak,
        "goal": goal,
        "celebrate": bool(closing == "celebrate" and settings.celebrate and plan.celebrated_at is None),
        "tomorrow": None,  # the web asks `preview/` for it: computing it here would run every provider on every read
    }
    if not lite:
        payload["week"] = [
            {**row, "date": row["date"].isoformat()} for row in selectors.week_strip(user_id, plan.local_date)
        ]
    return payload


def empty_state_payload(state: str, *, local_date: date, tz: str, now: datetime) -> dict:
    """`open/` for a student with no enrolment or past the exam: a state and no plan."""
    return {
        "version": PLAN_VERSION,
        "date": local_date.isoformat(),
        "tz": tz,
        "server_time": now.isoformat(),
        "state": state,
        "plan": None,
    }


def etag_of(payload: dict) -> str:
    """Stable for equal content: the clock is left out, so a repeated read of an unchanged plan answers 304."""
    body = {k: v for k, v in payload.items() if k != "server_time"}
    return 'W/"' + hashlib.sha1(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()[:20] + '"'


def preview_payload(user_id, gen, own_tasks, *, now: datetime) -> dict:
    """Up to four of the tasks the plan would hold on that day, with their minutes, plus the student's own tasks. Nothing is stored."""
    shown = gen.selection.picks[: c.PREVIEW_MAX_TASKS]
    return {
        "version": PLAN_VERSION,
        "date": gen.ctx.local_date.isoformat(),
        "tz": gen.ctx.tz,
        "server_time": now.isoformat(),
        "phase": gen.ctx.phase,
        "days_to_exam": gen.ctx.days_to_exam,
        "count": len(shown),
        "minutes": sum(p.candidate.est_minutes for p in shown),
        "tasks": [
            {
                "kind": p.candidate.kind,
                "slot": p.candidate.slot,
                "title": p.candidate.title,
                "reason": p.candidate.reason,
                "est_minutes": p.candidate.est_minutes,
                "subject_key": p.candidate.paper_key or "",
            }
            for p in shown
        ],
        "own_tasks": [
            {"id": str(t.id), "title": t.title, "est_minutes": t.est_minutes, "state": t.state} for t in own_tasks
        ],
    }


def history_payload(rows: list[dict], *, first: date, last: date, now: datetime) -> dict:
    return {
        "version": PLAN_VERSION,
        "server_time": now.isoformat(),
        "from": first.isoformat(),
        "to": last.isoformat(),
        "days": [{**row, "date": row["date"].isoformat()} for row in rows],
    }


def settings_payload(row: TodaySettings, *, now: datetime) -> dict:
    return {
        "version": PLAN_VERSION,
        "server_time": now.isoformat(),
        "minutes_per_day": row.minutes_per_day,
        "focus_papers": row.focus_papers,
        "disabled_kinds": list(row.disabled_kinds or []),
        "show_tomorrow": row.show_tomorrow,
        "celebrate": row.celebrate,
        "lite_mode": row.lite_mode,
    }


def counts_of(plan: DayPlan) -> dict:
    return {
        "planned": plan.planned_count,
        "done": plan.done_count,
        "open": plan.open_count,
        "skipped": plan.skipped_count,
        "snoozed": plan.snoozed_count,
    }


def task_response(task: Task, *, now: datetime, **extra) -> dict:
    """What a task action answers: the task, the plan's counters (so the ring updates without a refetch), and anything the action adds."""
    task.plan.refresh_from_db(fields=["planned_count", "done_count", "open_count", "skipped_count", "snoozed_count"])
    return {
        "version": PLAN_VERSION,
        "server_time": now.isoformat(),
        "task": task_dict(task),
        "counts": counts_of(task.plan),
        **extra,
    }
