"""Input validation (DRF) and output shapes for the student endpoints."""

from __future__ import annotations

from rest_framework import serializers

from core.authentication import SupabaseUser

from .avatar_urls import avatar_summary
from .domain.names import first_name, suggested_name
from .domain.onboarding import Resolution
from .selectors import Bootstrap

# --- input -----------------------------------------------------------------------------------


class MePatchSerializer(serializers.Serializer):
    """Only the name is writable. The deprecated course fields answer 400 `field_read_only` (handled by the view)."""

    full_name = serializers.CharField(trim_whitespace=False)

    DEPRECATED_FIELDS = ("course", "level", "exam_date")


class DeleteAccountSerializer(serializers.Serializer):
    confirm = serializers.CharField(allow_blank=True, default="")


# --- output ----------------------------------------------------------------------------------


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def onboarding_dict(r: Resolution) -> dict:
    return {
        "status": r.status.value,
        "mode": r.mode,
        "required_version": r.required_version,
        "completed_version": r.completed_version,
        "next_step": r.next_step,
        "missing": r.missing,
    }


def steps_dict(r: Resolution) -> dict:
    return {
        **onboarding_dict(r),
        "steps": [
            {
                "key": s.key,
                "state": s.state.value,
                "mandatory": s.mandatory,
                "available": s.state.value != "unavailable",
            }
            for s in r.steps
        ],
    }


def course_dict(summary) -> dict | None:
    if summary is None:
        return None
    return {
        "course": {"code": summary.course_code, "name": summary.course_name},
        "level": {"code": summary.level_code, "name": summary.level_name},
        "term": {"code": summary.term_code, "name": summary.term_name} if summary.term_code else None,
        "exam_date": _iso(summary.exam_date),
        "days_remaining": summary.days_remaining,
        "daily_minutes": summary.daily_minutes,
    }


def bootstrap_dict(b: Bootstrap, user: SupabaseUser) -> dict:
    p = b.profile
    return {
        "id": str(p.id),
        "email": p.email,
        "full_name": p.full_name,
        "first_name": first_name(p.full_name),
        # Prefill for the name field; never stored until the student confirms it in onboarding.
        "name_suggestion": suggested_name(user.claims, p.email),
        "avatar": avatar_summary(p),
        "onboarding": onboarding_dict(b.resolution),
        "course": course_dict(b.course),
        "last_visit": None
        if b.last_visit is None
        else {"path": b.last_visit.path, "search": b.last_visit.search, "at": _iso(b.last_visit.visited_at)},
        "created_at": _iso(p.created_at),
    }
