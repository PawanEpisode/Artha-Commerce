"""
Writes for the R2 study planner (PRD slice 17, FR-F13-47 to FR-F13-49). The pure planner (`planner/`) does the arithmetic; this file
loads the student's data, calls it and stores the result.

- `create_plan`: idempotent. The first call builds the plan (frozen reading deadline, milestones, health); a later call returns it,
  or re-plans when the exam date moved or the student gave other daily minutes.
- `replan`: one re-plan for a trigger. Nothing short: the new dates apply and a note says what moved. A shortfall: the dates are a
  proposal and the options wait for the student (`choose_option`); only the numbers and finished reading are stored meanwhile.
- `choose_option`: applies exactly the option the student picked, or keeps the plan as it is (`none`).
- `mark_reading_done`: a paper whose last chapter is read gets its `finish_reading` milestone done on that day, not at the weekly check.
- `sync_enrollment`: the course changed under the plan (another scheme, a new exam date).

Single flight per student: every write takes one advisory lock, so two tabs or the cron tick and a tap make one re-plan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from django.db import transaction
from django.utils import timezone

from core import events

from . import generation, planner_selectors, selectors, services
from .adapters import coverage as coverage_adapter
from .adapters import syllabus as syllabus_adapter
from .errors import (
    OptionExpired,
    OptionNotAvailable,
    PlannerNotReady,
    ReplanEventNotFound,
    StudyPlanNotFound,
)
from .models import Milestone, ReplanEvent, StudyPlan
from .planner import capacity as cap
from .planner import constants as pc
from .planner import milestones as ms
from .planner import options as op
from .planner import replan as rp

logger = logging.getLogger(__name__)

PLAN_CREATED = "today_planner_created"
PLAN_REPLANNED = "today_plan_replanned"
OPTION_CHOSEN = "today_replan_option_chosen"

LOCK_DAY = date(2000, 1, 1)  # the advisory lock of the planner is (student, this fixed day), apart from every plan day
NEW_ROW_STATUSES = ("pending", "at_risk", "done")


@dataclass(frozen=True)
class PlanResult:
    plan: StudyPlan
    created: bool
    event: ReplanEvent | None = None


@dataclass(frozen=True)
class Inputs:
    """What the pure planner needs, read once."""

    enrollment: object
    tz: str
    today: date
    exam: date
    papers: list[cap.PaperInput]
    chapters: list[cap.ChapterInput]
    subject_ids: dict[str, object]


# ---- loading ----------------------------------------------------------------------------------------------------------------


def _not_ready(reason: str) -> PlannerNotReady:
    messages = {
        "not_enrolled": "Choose your course to plan your study.",
        "no_exam_date": "Pick your exam attempt to plan your study.",
        "post_exam": "Your exam date has passed. Pick your next attempt to plan again.",
        "no_daily_minutes": "Tell us how long you can study each day.",
    }
    return PlannerNotReady(messages[reason], extra={"reason": reason})


def _load(user_id, now: datetime, skimmed: set[str]) -> Inputs:
    today, tz = generation.student_today(user_id, now)
    enrollment = coverage_adapter.active_enrollment(user_id)
    if enrollment is None:
        raise _not_ready("not_enrolled")
    exam = coverage_adapter.exam_date(enrollment)
    if exam is None:
        raise _not_ready("no_exam_date")
    if exam <= today:
        raise _not_ready("post_exam")
    state = coverage_adapter.study_state(user_id, enrollment, tz)
    papers: list[cap.PaperInput] = []
    chapters: list[cap.ChapterInput] = []
    subject_ids: dict[str, object] = {}
    for subject in state.subjects:
        subject_ids[subject.key] = subject.subject_id
        papers.append(cap.PaperInput(subject.key, subject.paper_number))
        for chapter in subject.chapters:
            chapters.append(
                cap.ChapterInput(
                    key=chapter.key,
                    subject_key=subject.key,
                    est_minutes=chapter.est_study_minutes,
                    read_pct=chapter.read_pct,
                    marks_weight=chapter.marks_weight,
                    skim=chapter.key in skimmed,
                )
            )
    return Inputs(enrollment, tz, today, exam, papers, chapters, subject_ids)


def _plan_params(plan: StudyPlan, today: date) -> cap.PlanParams:
    stored = plan.params or {}
    return cap.PlanParams(
        today=today,
        exam_date=plan.exam_date,
        daily_minutes=plan.daily_minutes,
        utilisation_pct=plan.utilisation_pct,
        learn_share_pct=stored.get("learn_share", pc.LEARN_SHARE_PCT_DEFAULT),
        lanes=stored.get("lanes", pc.LANES_DEFAULT),
        exam_week_days=stored.get("exam_week_days", pc.EXAM_WEEK_DAYS_DEFAULT),
        reading_deadline=plan.reading_deadline,
    )


def _params_json(params: cap.PlanParams, skimmed) -> dict:
    """`StudyPlan.params`. The skim list is cut to fit the column; a cut chapter simply counts in full again, which the health shows."""
    import json

    body = {
        "v": pc.PLANNER_VERSION,
        "learn_share": params.learn_share_pct,
        "exam_week_days": params.exam_week_days,
        "lanes": params.lanes,
        "skimmed": [],
    }
    for key in sorted(skimmed):
        body["skimmed"].append(key)
        if len(json.dumps(body)) > pc.PARAMS_MAX_CHARS:
            body["skimmed"].pop()
            break
    return body


def _previous_rows(plan: StudyPlan) -> list[ms.MilestoneRow]:
    return [
        ms.MilestoneRow(m.subject_key, m.kind, m.target_date, m.remaining_minutes, m.status, m.sort_order)
        for m in plan.milestones.all()
    ]


def _default_daily(user_id, enrollment) -> int:
    minutes = coverage_adapter.daily_minutes(enrollment) or selectors.get_settings(user_id).minutes_per_day
    if not minutes:
        raise _not_ready("no_daily_minutes")
    return max(pc.DAILY_MINUTES_MIN, min(pc.DAILY_MINUTES_MAX, int(minutes)))


# ---- storing ----------------------------------------------------------------------------------------------------------------


def _set_numbers(plan: StudyPlan, computation: rp.PlanComputation, now: datetime) -> None:
    capacity = computation.capacity
    plan.capacity_minutes = capacity.capacity_minutes
    plan.remaining_minutes = capacity.remaining_minutes
    plan.shortfall_minutes = max(0, capacity.remaining_minutes - capacity.capacity_minutes)  # the database checks this
    plan.health = computation.health.health
    plan.revise_until = capacity.revise_until
    plan.health_checked_at = now


def _store_milestones(
    plan: StudyPlan,
    rows,
    orphaned,
    subject_ids,
    now: datetime,
    *,
    apply_dates: bool,
) -> None:
    """Write the merged rows. Without `apply_dates` (a proposal) only finished reading, new papers and the minutes left are stored."""
    existing = {(m.kind, m.subject_key): m for m in plan.milestones.select_for_update()}
    created: list[Milestone] = []
    changed: list[Milestone] = []
    for row in rows:
        stored = existing.get(row.identity)
        if stored is None:
            created.append(
                Milestone(
                    plan=plan,
                    user_id=plan.user_id,
                    subject_id=subject_ids.get(row.subject_key),
                    subject_key=row.subject_key,
                    kind=row.kind,
                    target_date=row.target_date,
                    original_target_date=row.target_date,
                    remaining_minutes=row.remaining_minutes,
                    status=row.status if row.status in NEW_ROW_STATUSES else "pending",
                    done_at=now if row.status == "done" else None,
                    sort_order=row.sort_order,
                    replan_no=plan.replan_no,
                )
            )
            continue
        if stored.status in rp.FROZEN_STATUSES:
            if apply_dates and stored.sort_order != row.sort_order:
                stored.sort_order = row.sort_order
                changed.append(stored)
            continue
        before = (stored.target_date, stored.status, stored.remaining_minutes, stored.sort_order)
        if row.status == "done":
            stored.status, stored.done_at = "done", now
            stored.target_date, stored.remaining_minutes = row.target_date, 0
        else:
            stored.remaining_minutes = row.remaining_minutes
            if apply_dates:
                stored.target_date, stored.status, stored.sort_order = row.target_date, row.status, row.sort_order
        if before != (stored.target_date, stored.status, stored.remaining_minutes, stored.sort_order):
            stored.replan_no = plan.replan_no
            changed.append(stored)
    for row in orphaned:  # a paper left the course: the milestone is dropped, visibly, never deleted
        stored = existing.get(row.identity)
        if stored is not None and stored.status not in rp.FROZEN_STATUSES:
            stored.status, stored.replan_no = "dropped", plan.replan_no
            changed.append(stored)
    if created:
        Milestone.objects.bulk_create(created)
    if changed:
        for m in changed:
            m.updated_at = now  # `bulk_update` does not run `auto_now`
        Milestone.objects.bulk_update(
            changed,
            ["target_date", "status", "done_at", "remaining_minutes", "sort_order", "replan_no", "updated_at"],
        )


def _announce(name: str, **props) -> None:
    transaction.on_commit(lambda: events.emit(name, **props))


# ---- create -----------------------------------------------------------------------------------------------------------------


def create_plan(user_id, *, daily_minutes: int | None = None, now: datetime | None = None) -> PlanResult:
    """The student's plan for the active course. A second call changes nothing, unless the exam date or the daily minutes differ."""
    now = now or timezone.now()
    with transaction.atomic():
        services._lock(user_id, LOCK_DAY)
        plan = StudyPlan.objects.select_for_update().filter(user_id=user_id, status="active").first()
        enrollment = coverage_adapter.active_enrollment(user_id)
        if plan is not None and enrollment is not None and plan.enrollment_id == enrollment.id:
            changed_exam = coverage_adapter.exam_date(enrollment) not in (None, plan.exam_date)
            changed_daily = daily_minutes is not None and daily_minutes != plan.daily_minutes
            if not (changed_exam or changed_daily):
                return PlanResult(plan, False)
            trigger = "exam_date" if changed_exam else "manual"
            return _replan_locked(plan, now, trigger, daily_minutes=daily_minutes)
        previous = plan
        inputs = _load(user_id, now, set())
        minutes = daily_minutes or _default_daily(user_id, inputs.enrollment)
        params = cap.freeze_deadline(cap.PlanParams(today=inputs.today, exam_date=inputs.exam, daily_minutes=minutes))
        computation = rp.build_plan(params, inputs.papers, inputs.chapters)
        if previous is not None:  # another course or scheme is active now: the old plan is history
            previous.status = "superseded"
            previous.save(update_fields=["status", "updated_at"])
        plan = StudyPlan(
            user_id=user_id,
            enrollment_id=inputs.enrollment.id,
            scheme_id=inputs.enrollment.scheme_id,
            exam_date=inputs.exam,
            daily_minutes=minutes,
            utilisation_pct=params.utilisation_pct,
            reading_deadline=params.reading_deadline,
            params=_params_json(params, set()),
        )
        _set_numbers(plan, computation, now)
        plan.save()
        _store_milestones(plan, computation.milestones, (), inputs.subject_ids, now, apply_dates=True)
        event = None
        if previous is not None:
            event = ReplanEvent.objects.create(
                plan=plan,
                user_id=user_id,
                trigger="scheme_switch",
                health_before=previous.health,
                health_after=plan.health,
                shortfall_before=previous.shortfall_minutes,
                shortfall_after=plan.shortfall_minutes,
                summary={"v": pc.PLANNER_VERSION, "moved": [], "options": []},
            )
        _announce(
            PLAN_CREATED,
            user_id=str(user_id),
            health=plan.health,
            paper_count=len(inputs.papers),
            milestone_count=len(computation.milestones),
            scheme_switch=previous is not None,
        )
    return PlanResult(plan, True, event)


# ---- re-plan ----------------------------------------------------------------------------------------------------------------


def _skimmed_of(plan: StudyPlan) -> set[str]:
    return set((plan.params or {}).get("skimmed") or ())


def _replan_locked(
    plan: StudyPlan,
    now: datetime,
    trigger: str,
    *,
    daily_minutes: int | None = None,
) -> PlanResult:
    """One re-plan, with the plan row locked and the planner lock held."""
    user_id = plan.user_id
    inputs = _load(user_id, now, _skimmed_of(plan))
    params = _plan_params(plan, inputs.today)
    student_changed = False
    if inputs.exam != plan.exam_date:
        params = cap.freeze_deadline(params.but(exam_date=inputs.exam, reading_deadline=None))
        student_changed = True
    if daily_minutes is not None and daily_minutes != plan.daily_minutes:
        params = params.but(daily_minutes=daily_minutes)
        student_changed = True
    if params.reading_deadline is None:  # a plan stored without one (a hand-made row): freeze it now, once
        params = cap.freeze_deadline(params)

    result = rp.replan(
        _previous_rows(plan),
        params,
        inputs.papers,
        inputs.chapters,
        health_before=plan.health,
        shortfall_before=plan.shortfall_minutes,
        next_exam_date=syllabus_adapter.next_attempt_start(inputs.enrollment, inputs.exam),
    )
    apply_dates = result.auto_apply or student_changed or trigger == "scheme_switch"
    plan.replan_no += 1
    plan.exam_date, plan.daily_minutes = params.exam_date, params.daily_minutes
    plan.reading_deadline = params.reading_deadline
    plan.params = _params_json(params, _skimmed_of(plan))
    plan.last_replanned_at = now
    _set_numbers(plan, result.plan, now)
    plan.version += 1
    plan.save()
    _store_milestones(plan, result.plan.milestones, result.orphaned, inputs.subject_ids, now, apply_dates=apply_dates)

    nothing_new = not (result.moved or result.completed or result.added or result.orphaned or student_changed) and (
        result.health_after,
        result.shortfall_after,
    ) == (result.health_before, result.shortfall_before)
    event = None
    if trigger == "manual" or not nothing_new:
        event = ReplanEvent.objects.create(
            plan=plan,
            user_id=user_id,
            trigger=trigger,
            health_before=result.health_before,
            health_after=result.health_after,
            shortfall_before=result.shortfall_before,
            shortfall_after=result.shortfall_after,
            moved_count=result.moved_count,
            summary=rp.summary_json(result),
        )
        _announce(
            PLAN_REPLANNED,
            user_id=str(user_id),
            trigger=trigger,
            health_before=result.health_before,
            health_after=result.health_after,
            moved_count=result.moved_count,
            option_count=len(result.options),
            applied=apply_dates,
        )
    return PlanResult(plan, False, event)


def replan(user_id, *, trigger: str = "manual", now: datetime | None = None) -> PlanResult:
    """A re-plan for `trigger`. A student's own request (`manual`) always records an event; an automatic one records only a change."""
    now = now or timezone.now()
    with transaction.atomic():
        services._lock(user_id, LOCK_DAY)
        plan = StudyPlan.objects.select_for_update().filter(user_id=user_id, status="active").first()
        if plan is None:
            raise StudyPlanNotFound
        return _replan_locked(plan, now, trigger)


# ---- the student chooses ----------------------------------------------------------------------------------------------------


def choose_option(user_id, event_id, option: str, *, now: datetime | None = None) -> PlanResult:
    """Applies the option the student picked from the latest re-plan; `none` keeps the plan as it is. Applied once, never twice."""
    now = now or timezone.now()
    with transaction.atomic():
        services._lock(user_id, LOCK_DAY)
        event = planner_selectors.event_of(user_id, event_id)
        if event is None:
            raise ReplanEventNotFound
        plan = StudyPlan.objects.select_for_update().get(pk=event.plan_id)
        latest = planner_selectors.latest_event(plan)
        if plan.status != "active" or latest is None or latest.pk != event.pk or event.option_chosen is not None:
            raise OptionExpired
        shown = {o["option"]: o for o in event.summary.get("options", [])}
        if option != "none" and not (option in shown and shown[option].get("feasible")):
            raise OptionNotAvailable
        if option == "none":
            event.option_chosen = "none"
            event.save(update_fields=["option_chosen"])
            _announce(OPTION_CHOSEN, user_id=str(user_id), option="none", health_after=plan.health)
            return PlanResult(plan, False, event)

        skimmed = _skimmed_of(plan)
        inputs = _load(user_id, now, skimmed)
        params = _plan_params(plan, inputs.today)
        new_params, new_chapters = op.apply_option(params, inputs.chapters, shown[option])
        if option == "next_attempt":
            # the exam date is the student's course setting (F-03): it changes there, then the plan follows
            coverage_adapter.set_exam_date(inputs.enrollment, new_params.exam_date)
            new_params = cap.freeze_deadline(new_params.but(reading_deadline=None))
        skimmed |= {c.key for c in new_chapters if c.skim}
        merged = rp.replan(
            _previous_rows(plan),
            new_params,
            inputs.papers,
            new_chapters,
            health_before=plan.health,
            shortfall_before=plan.shortfall_minutes,
        )
        plan.replan_no += 1
        plan.exam_date, plan.daily_minutes = new_params.exam_date, new_params.daily_minutes
        plan.reading_deadline = new_params.reading_deadline
        plan.params = _params_json(new_params, skimmed)
        plan.last_replanned_at = now
        _set_numbers(plan, merged.plan, now)
        plan.version += 1
        plan.save()
        _store_milestones(plan, merged.plan.milestones, merged.orphaned, inputs.subject_ids, now, apply_dates=True)
        event.option_chosen = option
        event.health_after, event.shortfall_after = plan.health, merged.shortfall_after
        event.save(update_fields=["option_chosen", "health_after", "shortfall_after"])
        _announce(OPTION_CHOSEN, user_id=str(user_id), option=option, health_after=plan.health)
    return PlanResult(plan, False, event)


# ---- progress and course changes --------------------------------------------------------------------------------------------


def mark_reading_done(user_id, *, now: datetime | None = None) -> int:
    """
    A paper whose last chapter is read has its `finish_reading` milestone done on that day (W7 note: not at the weekly re-plan).
    The first revision follows on the next re-plan. Cheap for a student without a plan (one indexed query). Returns the count marked.
    """
    now = now or timezone.now()
    if not Milestone.objects.filter(
        user_id=user_id, kind="finish_reading", status__in=pc.OPEN_MILESTONE_STATUSES
    ).exists():
        return 0
    with transaction.atomic():
        services._lock(user_id, LOCK_DAY)
        plan = StudyPlan.objects.select_for_update().filter(user_id=user_id, status="active").first()
        if plan is None:
            return 0
        enrollment = coverage_adapter.active_enrollment(user_id)
        if enrollment is None or enrollment.id != plan.enrollment_id:
            return 0
        today, tz = generation.student_today(user_id, now)
        state = coverage_adapter.study_state(user_id, enrollment, tz)
        left = cap.remaining_by_paper(
            [
                cap.ChapterInput(
                    c.key, s.key, c.est_study_minutes, c.read_pct, c.marks_weight, skim=c.key in _skimmed_of(plan)
                )
                for s in state.subjects
                for c in s.chapters
            ]
        )
        marked = 0
        for m in plan.milestones.select_for_update().filter(
            kind="finish_reading", status__in=pc.OPEN_MILESTONE_STATUSES
        ):
            if m.subject_key in left and left[m.subject_key] == 0:
                m.status, m.done_at, m.target_date, m.remaining_minutes = "done", now, today, 0
                m.replan_no = plan.replan_no
                m.save()
                marked += 1
        if marked:
            plan.version += 1
            plan.save(update_fields=["version", "updated_at"])
    return marked


def sync_enrollment(user_id, *, now: datetime | None = None) -> PlanResult | None:
    """A new exam date or another scheme under an existing plan: re-plan on the date, or start the new course's plan. No plan: nothing."""
    now = now or timezone.now()
    if not StudyPlan.objects.filter(user_id=user_id, status="active").exists():
        return None
    try:
        return create_plan(user_id, now=now)
    except PlannerNotReady:
        return None  # no exam date, or it passed: the plan waits (the tick archives a finished one)


# ---- the clock --------------------------------------------------------------------------------------------------------------


def auto_replan(user_id, *, now: datetime | None = None) -> str:
    """
    One automatic check for the cron tick: re-plan when a trigger applies (2 missed days, Monday, 3 days since the last one),
    otherwise only refresh the health numbers, which change every day as the reading window shrinks. Returns what happened:
    the trigger, `refreshed`, `archived` (the exam passed) or `none` (no active plan).
    """
    now = now or timezone.now()
    with transaction.atomic():
        services._lock(user_id, LOCK_DAY)
        plan = StudyPlan.objects.select_for_update().filter(user_id=user_id, status="active").first()
        if plan is None:
            return "none"
        today, tz = generation.student_today(user_id, now)
        if plan.exam_date <= today:
            plan.status = "archived"
            plan.save(update_fields=["status", "updated_at"])
            return "archived"
        since = tracking_local_date(plan.created_at, tz)
        last = tracking_local_date(plan.last_replanned_at, tz) if plan.last_replanned_at else None
        missed = rp.consecutive_missed_days(planner_selectors.active_days(user_id, since, today), today, since)
        trigger = rp.should_replan(today=today, missed_days=missed, last_replanned_on=last)
        if trigger is not None:
            _replan_locked(plan, now, trigger)
            return trigger
        inputs = _load(user_id, now, _skimmed_of(plan))
        computation = rp.build_plan(_plan_params(plan, inputs.today), inputs.papers, inputs.chapters)
        _set_numbers(plan, computation, now)
        plan.save()
        return "refreshed"


def tracking_local_date(moment, tz: str) -> date:
    from .adapters import tracking as tracking_adapter

    return tracking_adapter.local_date(moment, tz)
