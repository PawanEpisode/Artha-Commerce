"""Input validation (DRF serializers) and output shapes (plain presenters) for coverage."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from modules.syllabus import selectors as syllabus
from modules.syllabus.models import ExamTerm
from modules.syllabus.serializers import elective_slot_data

from . import selectors
from .models import ChapterProgress, CoverageEvent, CoverageSettings, Enrollment, Rollup

# --- input -----------------------------------------------------------------------------------


class ElectiveChoicesField(serializers.DictField):
    """slot key -> chosen subject id, or null to clear the choice."""

    child = serializers.UUIDField(allow_null=True)


class EnrollmentCreateSerializer(serializers.Serializer):
    scheme = serializers.UUIDField()
    electives = ElectiveChoicesField(required=False)
    target_term = serializers.UUIDField(required=False, allow_null=True)
    exam_date = serializers.DateField(required=False, allow_null=True)
    daily_hours = serializers.DecimalField(
        max_digits=3, decimal_places=1, min_value=Decimal("0.5"), max_value=24, required=False, allow_null=True
    )


class EnrollmentPatchSerializer(serializers.Serializer):
    target_term = serializers.PrimaryKeyRelatedField(queryset=ExamTerm.objects.all(), required=False, allow_null=True)
    exam_date = serializers.DateField(required=False, allow_null=True)
    daily_hours = serializers.DecimalField(
        max_digits=3, decimal_places=1, min_value=Decimal("0.5"), max_value=24, required=False, allow_null=True
    )
    archive = serializers.BooleanField(required=False)
    scheme = serializers.UUIDField(required=False)


class ElectivesSerializer(serializers.Serializer):
    choices = ElectiveChoicesField()


class TickSerializer(serializers.Serializer):
    done = serializers.BooleanField()
    client_id = serializers.UUIDField(required=False, allow_null=True)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)


class CatchupSerializer(serializers.Serializer):
    chapter_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=300)
    also_revised = serializers.BooleanField(required=False, default=False)
    client_id = serializers.UUIDField(required=False, allow_null=True)


class EventCreateSerializer(serializers.Serializer):
    chapter_id = serializers.UUIDField()
    type = serializers.ChoiceField(choices=["practice_done", "mock_done", "revision_done"])
    value = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100, required=False, allow_null=True
    )
    client_id = serializers.UUIDField(required=False, allow_null=True)
    occurred_at = serializers.DateTimeField(required=False, allow_null=True)


class ConfidenceSerializer(serializers.Serializer):
    confidence = serializers.ChoiceField(choices=["red", "amber", "green"], allow_null=True)


class ExclusionSerializer(serializers.Serializer):
    excluded = serializers.BooleanField()


class SettingsSerializer(serializers.Serializer):
    w_read = serializers.IntegerField(min_value=0, max_value=100)
    w_practice = serializers.IntegerField(min_value=0, max_value=100)
    w_revise = serializers.IntegerField(min_value=0, max_value=100)
    w_mock = serializers.IntegerField(min_value=0, max_value=100)
    revision_days = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=365), min_length=1, max_length=8
    )
    weighted_default = serializers.BooleanField(required=False, default=False)


class TodaySerializer(serializers.Serializer):
    today = serializers.DateField(required=False)


# --- output ----------------------------------------------------------------------------------


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def rollup_dict(r: Rollup | None) -> dict:
    if r is None:
        return {"pct_simple": 0, "pct_weighted": 0, "chapters_total": 0, "chapters_done": 0, "chapters_started": 0}
    return {
        "pct_simple": r.pct_simple,
        "pct_weighted": r.pct_weighted,
        "chapters_total": r.chapters_total,
        "chapters_done": r.chapters_done,
        "chapters_started": r.chapters_started,
    }


def settings_dict(s: CoverageSettings) -> dict:
    return {
        "w_read": s.w_read,
        "w_practice": s.w_practice,
        "w_revise": s.w_revise,
        "w_mock": s.w_mock,
        "revision_days": selectors.revision_days_of(s),
        "weighted_default": s.weighted_default,
    }


def _electives_pending(e: Enrollment) -> int:
    """How many elective papers the student still has to choose."""
    chosen = {x.slot_key for x in e.electives.all()}
    return sum(1 for slot in syllabus.elective_slots(e.scheme) if slot.key not in chosen)


def enrollment_dict(e: Enrollment, today: date | None = None) -> dict:
    today = today or timezone.now().date()
    exam_date = e.exam_date or (e.target_term.exam_start if e.target_term else None)
    return {
        "id": str(e.id),
        "status": e.status,
        "course": {"code": e.scheme.level.course.code, "name": e.scheme.level.course.name},
        "level": {"id": str(e.scheme.level_id), "code": e.scheme.level.code, "name": e.scheme.level.name},
        "scheme": {"id": str(e.scheme_id), "code": e.scheme.code, "name": e.scheme.name},
        "target_term": {"id": str(e.target_term.id), "code": e.target_term.code, "name": e.target_term.name}
        if e.target_term
        else None,
        "exam_date": _iso(e.exam_date),
        "days_remaining": max((exam_date - today).days, 0) if exam_date else None,
        "daily_hours": float(e.daily_hours) if e.daily_hours is not None else None,
        "carried_from": str(e.carried_from_id) if e.carried_from_id else None,
        "electives_pending": _electives_pending(e),
        "created_at": _iso(e.created_at),
    }


def chapter_row(chapter, progress: ChapterProgress | None, counts: tuple[int, int]) -> dict:
    total, done = counts
    if progress is not None and total == 0:
        total, done = 1, int(progress.implicit_topic_done)
    elif total == 0:
        total = 1
    p = progress
    return {
        "id": str(chapter.id),
        "key": chapter.key,
        "name": chapter.name,
        "section": chapter.section,
        "marks_min": float(chapter.marks_min) if chapter.marks_min is not None else None,
        "marks_max": float(chapter.marks_max) if chapter.marks_max is not None else None,
        "marks_weight": chapter.marks_weight,
        "has_topics": counts[0] > 0,
        "topics_total": total,
        "topics_done": done,
        "coverage_pct": p.coverage_pct if p else 0,
        "status": p.status if p else ChapterProgress.Status.NOT_STARTED,
        "confidence": (p.confidence or None) if p else None,
        "is_excluded": p.is_excluded if p else False,
        "components": {
            "read": p.read_pct if p else 0,
            "practice": p.practice_pct if p else 0,
            "revise": p.revise_pct if p else 0,
            "mock": p.mock_pct if p else 0,
        },
        "practice_count": p.practice_count if p else 0,
        "mock_count": p.mock_count if p else 0,
        "revision_count": p.revision_count if p else 0,
        # Clamped for display and with the "can the student log one more" answer; the counts above stay the facts.
        "activities": selectors.activity_summary(chapter, p),
        "confidence_gate": selectors.confidence_gate(p),
        "targets": {
            "practice": chapter.target_practice_sets,
            "revisions": chapter.target_revisions,
            "mocks": chapter.target_mocks,
        },
        "total_study_seconds": p.total_study_seconds if p else 0,
        "last_studied_at": _iso(p.last_studied_at) if p else None,
        "last_revised_at": _iso(p.last_revised_at) if p else None,
        "next_revision_due": _iso(p.next_revision_due) if p else None,
    }


def event_dict(e: CoverageEvent) -> dict:
    return {
        "id": str(e.id),
        "type": e.type,
        "value": float(e.value) if e.value is not None else None,
        "source": e.source,
        "occurred_at": _iso(e.occurred_at),
    }


def electives_list(enrollment: Enrollment, chosen: dict | None = None) -> list[dict]:
    """The enrolment's elective slots with the student's choice (`chosen` is a subject id or null)."""
    if chosen is None:
        chosen = {e.slot_key: e.subject_id for e in enrollment.electives.all()}
    return [
        {**elective_slot_data(slot), "chosen": str(chosen[slot.key]) if slot.key in chosen else None}
        for slot in syllabus.elective_slots(enrollment.scheme)
    ]


def overview_dict(enrollment: Enrollment, settings: CoverageSettings, today: date) -> dict:
    data = selectors.overview(enrollment)
    slot_of = {o.id: slot.key for slot in syllabus.elective_slots(enrollment.scheme) for o in slot.options}
    subject_rows = [
        {
            "id": str(s.id),
            "key": s.key,
            "name": s.name,
            "paper_number": s.paper_number,
            "total_marks": s.total_marks,
            "group_key": s.group.key if s.group_id else None,
            "elective_slot": slot_of.get(s.id),
            "excluded_chapters": excluded,
            **rollup_dict(r),
        }
        for s, r, excluded in data["subjects"]
    ]
    return {
        "enrollment": enrollment_dict(enrollment, today),
        "weighted_default": settings.weighted_default,
        "level": rollup_dict(data["level_rollup"]),
        "groups": [{"id": str(g.id), "key": g.key, "name": g.name, **rollup_dict(r)} for g, r in data["groups"]],
        "subjects": subject_rows,
        "electives": electives_list(enrollment),
        "due_count": len(selectors.due_for_revision(enrollment, today)),
    }
