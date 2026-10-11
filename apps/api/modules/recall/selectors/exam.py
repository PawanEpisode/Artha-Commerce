"""
Exam reads (R2-W1, PRD 4.7): the quick-revision set, the cram read-through, pacing and the exam block of the Today plan. Pure reads
over the student's own cards; the maths is `domain.exam`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from ..adapters import coverage as coverage_adapter
from ..domain import exam
from ..domain import limits as lim
from ..domain.scheduling import local_date_of, study_day_start
from ..errors import CramNotOpen, ExamPassed, NoExamDate
from ..models import RecallCard
from .study import Study, recent_seconds_per_review

SAMPLE = 5
BANNER_DAYS = 45  # the Today banner and the quick plan are offered this close to the exam


@dataclass(frozen=True)
class QuickResult:
    plan: exam.QuickPlan
    exam_at: datetime
    exam_date: date
    minutes_per_day: int
    median_seconds: float


def _scope(study: Study, subject_key: str | None = None):
    """Her active cards in the scheme she is enrolled in (cards outside it, and unlinked ones, are not "my chapters")."""
    scheme_id = coverage_adapter.active_scheme_id(study.user_id)
    qs = RecallCard.objects.filter(user_id=study.user_id, status="active", deleted_at__isnull=True)
    if scheme_id is None:
        return qs.none()
    qs = qs.filter(item__scheme_id=scheme_id)
    return qs.filter(subject_key=subject_key) if subject_key else qs


def require_exam(study: Study, exam_override: date | None = None) -> datetime:
    """The exam instant, or 422 `no_exam_date` / `exam_passed`. An override date (preview only) is read in her study clock."""
    exam_at = study.exam_at
    if exam_override is not None:
        exam_at = study_day_start(exam_override, study.tz, study.day_start_hour)
    if exam_at is None:
        raise NoExamDate
    if exam_at <= study.now:
        raise ExamPassed
    return exam_at


def quick_plan(
    study: Study, *, minutes: int | None = None, subject_key: str | None = None, exam_override: date | None = None
) -> QuickResult:
    exam_at = require_exam(study, exam_override)
    minutes = minutes or study.settings.quick_minutes_per_day
    median = recent_seconds_per_review(study.user_id, study.today, default=lim.DEFAULT_SECONDS_PER_CARD)
    rows = (
        _scope(study, subject_key)
        .filter(importance__gte=lim.QUICK_MIN_IMPORTANCE)
        .values_list("id", "importance", "state", "stability", "last_review_at", "chapter_id")
    )
    due = coverage_adapter.due_revision_chapter_ids(
        study.user_id, study.today
    )  # FR-F15-63: chapters due for revision go first
    cards = (
        exam.QuickCard(str(i), imp, state, stab, last, boosted=imp == exam.MANDATORY and chapter in due)
        for i, imp, state, stab, last, chapter in rows
    )
    plan = exam.quick_set(cards, exam_at, minutes, median, study.now, study.weights[20])
    return QuickResult(plan, exam_at, _date_of(study, exam_at), minutes, median)


def _date_of(study: Study, exam_at: datetime) -> date:
    return local_date_of(exam_at, study.tz, study.day_start_hour)


def cram_ids(study: Study) -> list[str]:
    """Mandatory cards of her chapters for the last-day read-through, the most likely forgotten first (unseen last)."""
    if not exam.cram_open(study.now, study.exam_at):
        raise CramNotOpen
    rows = (
        _scope(study)
        .filter(importance=2)
        .exclude(buried_until__gt=study.now)
        .values_list("id", "state", "stability", "last_review_at")
    )
    w20 = study.weights[20]
    scored = []
    for i, state, stab, last in rows:
        r = exam.r_exam(stab, last, study.exam_at, w20) if state else None
        scored.append((2.0 if r is None else r, str(i)))
    scored.sort()
    return [i for _, i in scored]


def pacing_for(study: Study) -> exam.Pacing | None:
    if study.exam_at is None or study.days_to_exam is None or study.days_to_exam <= 0:
        return None
    unseen = _scope(study).filter(state=0, importance__gte=lim.QUICK_MIN_IMPORTANCE).count()
    return exam.pacing(unseen, study.days_to_exam, study.settings.new_per_day)


def exam_context(study: Study) -> dict | None:
    """The `exam` block of the Today plan: countdown, the quick-revision banner, cram and pacing. None without a future exam."""
    left = study.days_to_exam
    if left is None or left <= 0:
        return None
    out: dict = {
        "exam_date": _date_of(study, study.exam_at).isoformat(),
        "days_to_exam": int(left),
        "quick": None,
        "cram_open": exam.cram_open(study.now, study.exam_at),
        "pacing": None,
    }
    if left <= BANNER_DAYS:
        result = quick_plan(study)
        p = result.plan
        out["quick"] = {
            "candidates": p.candidates,
            "selected": p.selected,
            "cut_off": p.cut_off,
            "per_day": p.per_day,
            "minutes_per_day": p.minutes_per_day,
            "too_few": p.too_few,
        }
    pacing = pacing_for(study) if left <= lim.EXAM_HORIZON_DAYS else None
    if pacing is not None and pacing.unseen:
        out["pacing"] = {
            "unseen": pacing.unseen,
            "window_days": pacing.window_days,
            "new_per_day": pacing.new_per_day,
            "introduced_at_limit": pacing.introduced_at_limit,
            "needed_per_day": pacing.needed_per_day,
            "feasible": pacing.feasible,
        }
    return out
