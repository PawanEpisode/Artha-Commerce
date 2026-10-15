"""
Writes for Today. `open_today` is the only way a plan comes into being from a student's action: idempotent (a second call returns the
same plan and the same task ids) and single flight per (student, local date), so two tabs opening at once make one plan (FR-F13-02).

Single flight: one transaction takes a PostgreSQL advisory lock for the (student, date) pair, re-reads the plan, and only then
generates. The second caller waits for the lock, finds the finished plan and returns it. The `(user_id, local_date)` unique
constraint is the backstop. Generation runs inside the lock on purpose: it takes about a second, and only the same student on the
same day waits for it.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime

from django.db import IntegrityError, connection, transaction
from django.db.models import F
from django.utils import timezone

from . import generation, registry, selectors
from .adapters import syllabus as syllabus_adapter
from .domain import constants as c
from .domain.week import recount
from .errors import InvalidDate
from .models import DayPlan, Task, TodaySettings

logger = logging.getLogger(__name__)

JSON_SAFE_CHARS = 3500  # the database limit is 4096 characters of rendered JSON; stay clear of it

NOT_ENROLLED, POST_EXAM, READY = "not_enrolled", "post_exam", "ready"


@dataclass(frozen=True)
class OpenResult:
    state: str  # ready, not_enrolled, post_exam
    plan: DayPlan | None
    created: bool
    local_date: date
    tz: str


# ---- helpers ----------------------------------------------------------------------------------------------------------------


def _lock(user_id, local_date: date) -> None:
    """Held until the transaction ends. A no-op off PostgreSQL (SQLite has one writer anyway)."""
    if connection.vendor != "postgresql":
        return
    digest = hashlib.sha1(f"today:{user_id}:{local_date.isoformat()}".encode()).digest()
    key = int.from_bytes(digest[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])


def _json_safe(value, limit: int = JSON_SAFE_CHARS, default=None):
    """A value that is plain JSON and small enough for the column check, else `default`."""
    try:
        clean = json.loads(json.dumps(value, default=str))
    except (TypeError, ValueError):
        return default if default is not None else {}
    return clean if len(json.dumps(clean)) <= limit else (default if default is not None else {})


def refresh_counters(plan: DayPlan) -> DayPlan:
    """Recomputes every counter from the live tasks (ERD 0.6: counters are recomputed, never incremented)."""
    rows = Task.objects.filter(plan=plan, deleted_at__isnull=True).exclude(state="expired")
    counters = recount(rows.values_list("state", "est_minutes", "counts_toward_day"))
    for name in (
        "planned_count",
        "done_count",
        "skipped_count",
        "open_count",
        "snoozed_count",
        "planned_minutes",
        "open_minutes",
    ):
        setattr(plan, name, getattr(counters, name))
    return plan


def _task_rows(plan: DayPlan, gen: generation.Generated, *, picks=None, offset: int = 0) -> list[Task]:
    papers = {p.key: p for p in gen.ctx.papers}
    picks = gen.selection.picks if picks is None else picks
    chapter_keys = syllabus_adapter.chapter_keys(
        gen.candidates_by_key[p.candidate.dedupe_key][1].chapter_id
        for p in picks
        if p.candidate.dedupe_key in gen.candidates_by_key
    )
    reasons = registry.reasons()
    rows = []
    for pick in picks:
        cand = pick.candidate
        spec, tc = gen.candidates_by_key[cand.dedupe_key]
        paper = papers.get(cand.paper_key) if cand.paper_key else None
        chapter_known = tc.chapter_id in chapter_keys
        action = None
        if tc.manual_action is not None and registry.manual_action(tc.manual_action.key) is not None:
            action = {
                "key": tc.manual_action.key,
                "label": tc.manual_action.label[:80],
                "default": bool(tc.manual_action.default_on),
            }
        rows.append(
            Task(
                user_id=plan.user_id,
                plan=plan,
                local_date=plan.local_date,
                origin="provider",
                provider=spec.name,
                kind=cand.kind,
                slot=cand.slot,
                dedupe_key=cand.dedupe_key,
                title=cand.title.strip(),
                reason_code=cand.reason_code if cand.reason_code in reasons else "custom",
                reason=(cand.reason or registry.reason_label(cand.reason_code))[: c.REASON_MAX],
                link_path=cand.link_path,
                link_search=_json_safe(dict(cand.link_search)),
                est_minutes=cand.est_minutes,
                subject_id=paper.subject_id if paper else None,
                chapter_id=tc.chapter_id if chapter_known else None,
                subject_key=paper.key if paper else "",
                chapter_key=chapter_keys.get(tc.chapter_id, "") if chapter_known else "",
                target_value=cand.target_value,
                position=offset + pick.position,
                is_must_do=pick.breakdown.get("must_do", False) is True,
                score=pick.score,
                score_breakdown=_json_safe(pick.breakdown),
                payload=_json_safe(dict(tc.payload)),
                manual_action=action,
            )
        )
    return rows


def plan_fields(gen: generation.Generated, now: datetime) -> dict:
    """The plan columns a generation decides (shared by the first open, a draft upgrade and a regeneration)."""
    ctx = gen.ctx
    selection_log = gen.selection.selection_log()
    selection_log["backlogs"] = {b["provider"]: b["count"] for b in gen.backlogs}
    return dict(
        tz=ctx.tz,
        status="ready",
        algorithm_version=c.ALGORITHM_VERSION,
        phase=ctx.phase,
        exam_date=gen.exam_date,
        days_to_exam=ctx.days_to_exam,
        budget_minutes=ctx.budget_minutes,
        budget_source=gen.budget_source,
        partial=gen.run.partial,
        provider_status=_json_safe(gen.run.status_map(), default={}),
        selection_log=_json_safe(selection_log, default={"v": 1}),
        context_hash=gen.context_hash,
        generated_at=now,
    )


def settle(plan: DayPlan) -> DayPlan:
    """Recount from the rows and bump the version. Call with the plan row locked, after the task rows changed."""
    refresh_counters(plan)
    plan.version += 1
    plan.save()
    return plan


def wake_snoozed(plan: DayPlan) -> int:
    """
    A student's own task that was snoozed to this day becomes a suggestion when the day opens (`move`, PRD 5.2). A provider task
    stays snoozed: its provider re-offers the work as a new task if it is still needed.
    """
    woken = Task.objects.filter(
        plan=plan, origin="user", state="snoozed", snoozed_until__lte=plan.local_date, deleted_at__isnull=True
    ).update(state="suggested", prev_state="snoozed", snoozed_until=None, version=F("version") + 1)
    if woken:
        settle(plan)
    return woken


def _persist(plan: DayPlan | None, gen: generation.Generated, user_id, now: datetime) -> DayPlan:
    ctx = gen.ctx
    fields = plan_fields(gen, now)
    fields["first_opened_at"] = now
    if plan is None:
        plan = DayPlan(user_id=user_id, local_date=ctx.local_date, generation_no=1, **fields)
    else:  # a draft made by the student's own first task for this day
        for name, value in fields.items():
            setattr(plan, name, value)
        plan.generation_no = max(plan.generation_no, 0) + 1
        # the student's own tasks stay, after the generated ones
        Task.objects.filter(plan=plan, deleted_at__isnull=True).update(
            position=F("position") + len(gen.selection.picks)
        )
    plan.save()
    Task.objects.bulk_create(_task_rows(plan, gen))
    refresh_counters(plan)
    plan.save()
    wake_snoozed(plan)
    return plan


# ---- open -------------------------------------------------------------------------------------------------------------------


def open_today(user_id, *, local_date: date | None = None, now: datetime | None = None) -> OpenResult:
    """
    Ensure the plan for the student's local day and return it. Creates nothing for a student with no enrolment (`not_enrolled`) or
    whose exam date has passed (`post_exam`): the web shows its own state, there is no plan to keep.
    """
    now = now or timezone.now()
    today, tz = generation.student_today(user_id, now)
    if local_date is not None and local_date != today:
        raise InvalidDate(
            "Open today's plan with your local date.", extra={"date": [f"Your local date is {today.isoformat()}."]}
        )
    day = today

    existing = selectors.get_plan(user_id, day)
    if existing is not None and existing.status != "draft":
        return OpenResult(READY, _refreshed(existing, now), False, day, tz)

    with transaction.atomic():
        _lock(user_id, day)
        plan = DayPlan.objects.select_for_update().filter(user_id=user_id, local_date=day).first()
        if plan is not None and plan.status != "draft":
            return OpenResult(
                READY, _refreshed(plan, now), False, day, tz
            )  # the other caller won the lock and finished
        gen = generation.generate(user_id, day, tz, plan=plan)
        if gen.ctx.enrollment is None:
            return OpenResult(NOT_ENROLLED, None, False, day, tz)
        if gen.ctx.phase == "post_exam":
            return OpenResult(POST_EXAM, None, False, day, tz)
        try:
            with transaction.atomic():
                saved = _persist(plan, gen, user_id, now)
        except IntegrityError:  # the unique constraint caught a race the lock could not (SQLite, a missed lock)
            logger.info("today: lost a plan race for %s on %s", user_id, day)
            saved = selectors.get_plan(user_id, day)
            return OpenResult(READY, saved, False, day, tz)
    return OpenResult(READY, saved, True, day, tz)


def _refreshed(plan: DayPlan, now: datetime) -> DayPlan:
    """
    What `open/` does for a plan that exists: stamp the first open, wake own tasks snoozed to today, and let each provider's
    `reconcile` complete tasks whose work the student already did (offline, another device, a missed event). `GET plan/` never
    does this: it stays a pure read (audit AUD-014), so the web opens first and reads after.
    """
    from . import completion  # a cycle at import time: completion needs this module's locks

    plan = _touch(plan, now)
    if plan.status == "ready":
        wake_snoozed(plan)
        if completion.reconcile_plan(plan, now=now):
            plan.refresh_from_db()
    return plan


def _touch(plan: DayPlan, now: datetime) -> DayPlan:
    """The first open of a plan that was pre-generated stamps `first_opened_at` (once, idempotent)."""
    if plan.first_opened_at is None:
        DayPlan.objects.filter(pk=plan.pk, first_opened_at__isnull=True).update(first_opened_at=now)
        plan.first_opened_at = now
    return plan


# ---- settings ---------------------------------------------------------------------------------------------------------------


def save_settings(user_id, values: dict) -> TodaySettings:
    """Creates the row on the first save. Keys left out stay as they are; `None` for minutes or focus papers means auto."""
    with transaction.atomic():
        row, _ = TodaySettings.objects.select_for_update().get_or_create(user_id=user_id)
        for name, value in values.items():
            setattr(row, name, value)
        row.save()
    return row


# ---- celebration ------------------------------------------------------------------------------------------------------------


def mark_celebrated(user_id, *, now: datetime | None = None) -> DayPlan | None:
    """
    Records that today's celebration was shown (`celebrated_at`, once per day across devices). Idempotent: the first call wins and a
    later one changes nothing. Returns None when there is no plan for the student's day.
    """
    now = now or timezone.now()
    today, _tz = generation.student_today(user_id, now)
    with transaction.atomic():
        plan = DayPlan.objects.select_for_update().filter(user_id=user_id, local_date=today).first()
        if plan is None or plan.status == "draft":
            return None
        if plan.celebrated_at is None:
            plan.celebrated_at = now
            plan.save(update_fields=["celebrated_at"])
    return plan
