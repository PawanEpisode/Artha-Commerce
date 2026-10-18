"""
Practice Engine Services (F-06 ERD 3.2, 3.4, 3.5).
"""

from __future__ import annotations

import random
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from core.events import emit_domain_event
from modules.questionbank import selectors as qb_selectors

from .domain.scoring import (
    NumericKey,
    OptionKey,
    ResolvedScoringRule,
    compute_negative_penalty,
    grade_choice,
    grade_numeric,
    resolve_scoring_rule,
)
from .domain.session import (
    calculate_deadline,
    feedback_policy_for_mode,
    pause_allowed,
    validate_transition,
)
from .models import (
    AttemptAnswer,
    DailyRollup,
    QuestionState,
    Session,
    Submission,
)
from .registry import PickContext, PickedItem, get_origin, get_picker


class PracticeError(Exception):
    """Base exception for Practice engine."""


class SessionNotFound(PracticeError, ValueError):
    """Session was not found or does not belong to user."""


class SessionClosed(PracticeError, ValueError):
    """Session is closed, submitted, or in a non-editable state."""


class AnswerLocked(PracticeError, ValueError):
    """Answer has been checked and locked."""


class InstantFeedbackDisabled(PracticeError, ValueError):
    """Instant feedback is not permitted for this session mode/policy."""


class ForbiddenRetake(PracticeError, ValueError):
    """Retake is not permitted for this session."""


class PauseNotAllowed(PracticeError, ValueError):
    """Pausing is not allowed for this session."""


class PickerEmpty(PracticeError, ValueError):
    """Picker returned 0 questions for the spec."""


class UnsupportedOrigin(PracticeError, ValueError):
    """Origin is not registered."""


class ModeNotAllowed(PracticeError, ValueError):
    """Mode is not allowed for this origin."""


@dataclass
class SessionCreated:
    session_id: uuid.UUID
    question_count: int
    title: str
    status: str
    mode: str
    total_marks: Decimal
    time_limit_seconds: int | None
    deadline_at: datetime | None
    feedback_policy: str = ""


@dataclass
class AnswerSaved:
    session_id: uuid.UUID
    position: int
    status: str
    time_spent_ms: int
    answer_id: uuid.UUID | None = None

    @property
    def id(self) -> uuid.UUID | None:
        return self.answer_id


@dataclass
class Feedback:
    result: str
    marks_awarded: Decimal
    negative_applied: Decimal
    explanation_md: str
    options_feedback: list[dict[str, Any]]


@dataclass
class SessionResult:
    session_id: uuid.UUID
    score: Decimal
    max_score: Decimal
    score_status: str
    counts: dict[str, int]
    by_chapter: list[dict[str, Any]]


def create_session(
    user_id: uuid.UUID | None = None,
    *,
    mode: str = "untimed",
    origin_module: str | None = None,
    origin: str | None = None,
    origin_ref: str | None = None,
    picker: str = "filter",
    spec: dict[str, Any] | None = None,
    picker_params: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    scoring_profile: str = "practice",
    time_limit_seconds: int | None = None,
    feedback_policy: str | None = None,
    title: str = "",
    client_id: uuid.UUID | None = None,
    tz: str = "Asia/Kolkata",
    retake_of_id: uuid.UUID | None = None,
    **kwargs: Any,
) -> SessionCreated:
    """Create a practice session atomically with pinned versions and frozen marks."""
    user_id = user_id or kwargs.get("user_id")
    origin_mod = origin or origin_module or "questionbank"
    actual_spec = dict(picker_params or spec or {})
    cfg = dict(config or {})
    if cfg:
        actual_spec.update(cfg)
        actual_spec.setdefault("config", {}).update(cfg)
    if "time_limit_seconds" in cfg:
        time_limit_seconds = cfg["time_limit_seconds"]
    if "feedback_policy" in cfg:
        feedback_policy = cfg["feedback_policy"]
    if "scoring_profile" in cfg:
        scoring_profile = cfg["scoring_profile"]

    cid = client_id or uuid.uuid4()
    if client_id:
        existing = Session.objects.filter(user_id=user_id, client_id=client_id).first()
        if existing:
            return SessionCreated(
                session_id=existing.id,
                question_count=existing.question_count,
                title=existing.title,
                status=existing.status,
                mode=existing.mode,
                total_marks=existing.total_marks,
                time_limit_seconds=existing.time_limit_seconds,
                deadline_at=existing.deadline_at,
                feedback_policy=existing.feedback_policy,
            )

    origin_spec = get_origin(origin_mod)
    if not origin_spec:
        raise UnsupportedOrigin(f"Unknown origin '{origin_mod}'.")

    if mode not in origin_spec.allowed_modes:
        raise ModeNotAllowed(f"Mode '{mode}' not permitted for origin '{origin_mod}'.")

    picker_fn = get_picker(picker)
    if not picker_fn:
        raise ValueError(f"Unknown picker '{picker}'.")

    resolved_policy = feedback_policy_for_mode(mode, feedback_policy or origin_spec.default_feedback_policy)

    # Shuffling seed
    shuffle_seed = random.randint(1, 1_000_000_000)
    rng = random.Random(shuffle_seed)

    count_requested = actual_spec.get("count", 20)
    ctx = PickContext(user_id=user_id, spec=actual_spec, rng=rng, limit=count_requested)
    picked_items: list[PickedItem] = picker_fn(ctx)

    if not picked_items:
        raise PickerEmpty("No questions available matching picker spec.")

    # Fetch gradables to get version_id, kind, marks, chapter_id, etc.
    refs = [(it.question_id, it.version_id) for it in picked_items]
    gradables = qb_selectors.get_gradables(refs)

    # Determine local date
    try:
        user_tz = ZoneInfo(tz)
    except Exception:
        user_tz = ZoneInfo("Asia/Kolkata")
    now = timezone.now()
    local_date = now.astimezone(user_tz).date()

    # Determine course / level / subject for scoring rule resolution from first item
    first_gradable = next(iter(gradables.values()), None)
    course_id = first_gradable.course_id if first_gradable else uuid.uuid4()
    level_id = first_gradable.level_id if first_gradable else None
    subject_key = first_gradable.subject_key if first_gradable else None

    rule: ResolvedScoringRule = resolve_scoring_rule(
        course_id=course_id,
        level_id=level_id,
        subject_key=subject_key,
        on_date=local_date,
        profile=scoring_profile,
    )
    scoring_snapshot = rule.to_snapshot()

    with transaction.atomic():
        # Compute total marks
        total_marks = Decimal("0.00")
        for it in picked_items:
            g = gradables.get(it.question_id)
            if g:
                item_marks = it.marks or g.marks
                total_marks += item_marks

        session = Session.objects.create(
            user_id=user_id,
            client_id=cid,
            mode=mode,
            origin_module=origin_mod,
            origin_ref=origin_ref,
            title=title,
            picker=picker,
            spec=actual_spec,
            status=Session.Status.CREATED,
            feedback_policy=resolved_policy,
            scoring_profile=scoring_profile,
            scoring_snapshot=scoring_snapshot,
            shuffle_seed=shuffle_seed,
            question_count=len(picked_items),
            total_marks=total_marks,
            time_limit_seconds=time_limit_seconds,
            tz=tz,
            local_date=local_date,
            retake_of_id=retake_of_id,
        )

        answer_rows = []
        for pos, it in enumerate(picked_items, start=1):
            g = gradables.get(it.question_id)
            if not g:
                continue

            marks_max = it.marks or g.marks
            if rule.rule_id is not None:
                negative_max = compute_negative_penalty(rule, marks_max)
            elif it.negative_marks is not None:
                negative_max = it.negative_marks
            elif g.negative_marks is not None:
                negative_max = g.negative_marks
            else:
                negative_max = compute_negative_penalty(rule, marks_max)
            ans_id = uuid.uuid5(session.id, str(pos))

            ans = AttemptAnswer(
                id=ans_id,
                created_at=session.created_at,
                session=session,
                user_id=user_id,
                position=pos,
                question_id=it.question_id,
                question_version_id=g.version_id,
                group_question_id=g.parent_id,
                kind=g.kind,
                chapter_id=g.chapter_id,
                subject_id=g.subject_id,
                section_label=it.section_label,
                status=AttemptAnswer.Status.UNSEEN,
                marks_max=marks_max,
                negative_max=negative_max,
            )
            answer_rows.append(ans)

        AttemptAnswer.objects.bulk_create(answer_rows)

        # Emit domain event
        emit_domain_event(
            "practice_session_started",
            {
                "session_id": str(session.id),
                "mode": session.mode,
                "origin_module": session.origin_module,
                "origin_ref": session.origin_ref,
                "question_count": session.question_count,
                "chapter_ids": [str(ans.chapter_id) for ans in answer_rows if ans.chapter_id],
                "time_limit_seconds": session.time_limit_seconds,
            },
            user_id=user_id,
            key=str(session.id),
        )

    return SessionCreated(
        session_id=session.id,
        question_count=session.question_count,
        title=session.title,
        status=session.status,
        mode=session.mode,
        total_marks=session.total_marks,
        time_limit_seconds=session.time_limit_seconds,
        deadline_at=session.deadline_at,
        feedback_policy=session.feedback_policy,
    )


def create_session_from_items(
    user_id: uuid.UUID | None = None,
    *,
    mode: str = "untimed",
    origin_module: str | None = None,
    origin: str | None = None,
    origin_ref: str | None = None,
    items: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
    time_limit_seconds: int | None = None,
    feedback_policy: str | None = None,
    scoring_profile: str = "official",
    client_id: uuid.UUID | None = None,
    tz: str = "Asia/Kolkata",
    title: str = "",
    retake_of_id: uuid.UUID | None = None,
    **kwargs: Any,
) -> SessionCreated:
    """Convenience helper for explicit question items (PYQ papers, mock papers)."""
    user_id = user_id or kwargs.get("user_id")
    origin_mod = origin or origin_module or "questionbank"
    return create_session(
        user_id=user_id,
        mode=mode,
        origin=origin_mod,
        origin_ref=origin_ref,
        picker="explicit_items",
        spec={"items": items},
        config=config,
        scoring_profile=scoring_profile,
        time_limit_seconds=time_limit_seconds,
        feedback_policy=feedback_policy,
        title=title,
        client_id=client_id,
        tz=tz,
        retake_of_id=retake_of_id,
    )


# A student's own submit or last answer can land a moment after the deadline; this keeps that race from losing work.
EXPIRY_GRACE_SECONDS = 5


def _is_overdue(session: Session, now: datetime) -> bool:
    return (
        session.status == Session.Status.IN_PROGRESS
        and session.deadline_at is not None
        and now > session.deadline_at + timedelta(seconds=EXPIRY_GRACE_SECONDS)
    )


def _expire_if_overdue(session: Session) -> bool:
    """Auto-submit a timed session whose deadline has passed. True when this call closed it."""
    if not _is_overdue(session, timezone.now()):
        return False
    submit_session(user_id=session.user_id, session_id=session.id, auto=True)
    return True


def expire_if_due(user_id: uuid.UUID, session_id: uuid.UUID) -> bool:
    """Close one session if its time ran out. Safe to call on every read."""
    session = Session.objects.filter(id=session_id, user_id=user_id).first()
    return _expire_if_overdue(session) if session else False


def expire_overdue_for_user(user_id: uuid.UUID) -> int:
    """Close this student's timed sessions that ran out while the tab was closed. Returns how many."""
    now = timezone.now()
    overdue = Session.objects.filter(
        user_id=user_id,
        status=Session.Status.IN_PROGRESS,
        deadline_at__lt=now - timedelta(seconds=EXPIRY_GRACE_SECONDS),
    )
    return sum(1 for session in overdue if _expire_if_overdue(session))


def expire_overdue_sessions(limit: int = 500) -> int:
    """Sweep for every student, for a scheduled job: sessions nobody opened again still get closed and scored."""
    now = timezone.now()
    overdue = Session.objects.filter(
        status=Session.Status.IN_PROGRESS,
        deadline_at__lt=now - timedelta(seconds=EXPIRY_GRACE_SECONDS),
    ).order_by("deadline_at")[:limit]
    return sum(1 for session in overdue if _expire_if_overdue(session))


def save_answer(
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    position: int | None = None,
    answer_data: dict[str, Any] | None = None,
    *,
    question_id: uuid.UUID | None = None,
    answer_json: dict[str, Any] | None = None,
    client_ts: Any = None,
    time_spent_ms: int = 0,
    confidence: str | None = None,
    flagged: bool | None = None,
    notes_md: str | None = None,
    **kwargs: Any,
) -> AnswerSaved:
    """Save an answer with last-write-wins semantics."""
    user_id = user_id or kwargs.get("user_id")
    session_id = session_id or kwargs.get("session_id")

    session = Session.objects.filter(id=session_id, user_id=user_id).first()
    if not session:
        raise SessionNotFound("Session not found.")

    if session.status in (Session.Status.SUBMITTED, Session.Status.AUTO_SUBMITTED, Session.Status.ABANDONED):
        raise SessionClosed(f"Cannot save answer on a {session.status} session.")
    if _expire_if_overdue(session):
        raise SessionClosed("Time is up. The session was submitted automatically.")

    now = timezone.now()
    if session.status == Session.Status.CREATED:
        session.status = Session.Status.IN_PROGRESS
        session.started_at = now
        session.deadline_at = calculate_deadline(now, session.time_limit_seconds, session.paused_total_seconds)
        session.save(update_fields=["status", "started_at", "deadline_at", "updated_at"])

    ans_qs = AttemptAnswer.objects.filter(session_id=session_id, user_id=user_id)
    if position is not None:
        ans = ans_qs.filter(position=position).first()
    elif question_id is not None:
        ans = ans_qs.filter(question_id=question_id).first()
    else:
        raise ValueError("Must provide position or question_id.")

    if not ans:
        raise ValueError("Answer row not found.")

    if ans.status == AttemptAnswer.Status.GRADED:
        raise AnswerLocked("Answer has already been checked and locked.")

    data = dict(answer_data or {})
    if answer_json is not None:
        data.update(answer_json)
    if time_spent_ms:
        data["time_spent_delta_ms"] = time_spent_ms
    if confidence:
        data["confidence"] = confidence
    if flagged is not None:
        data["marked_for_review"] = flagged
    if notes_md:
        data["notes_md"] = notes_md

    # Parse client_ts if string
    ts_dt = None
    if client_ts:
        if isinstance(client_ts, datetime):
            ts_dt = client_ts
        elif isinstance(client_ts, str):
            try:
                ts_dt = datetime.fromisoformat(client_ts)
            except Exception:
                ts_dt = None

    # Last write wins check
    if ts_dt and ans.client_ts and ts_dt < ans.client_ts:
        return AnswerSaved(
            session_id=session_id, position=ans.position, status=ans.status, time_spent_ms=ans.time_spent_ms
        )

    update_fields = ["status", "answer_changes", "last_active_at", "updated_at"]

    if "selected_option_ids" in data:
        ans.selected_option_ids = [str(x) for x in data["selected_option_ids"]]
        update_fields.append("selected_option_ids")

    if "numeric_value" in data:
        val = data["numeric_value"]
        ans.numeric_value = Decimal(str(val)) if val is not None else None
        ans.numeric_unit = data.get("numeric_unit")
        update_fields.extend(["numeric_value", "numeric_unit"])

    if "time_spent_delta_ms" in data:
        delta = min(int(data["time_spent_delta_ms"]), 600_000)  # clamp to 10 mins
        ans.time_spent_ms += delta
        session.active_seconds += delta // 1000
        update_fields.append("time_spent_ms")

    if "confidence" in data:
        ans.confidence = data["confidence"]
        update_fields.append("confidence")

    if "marked_for_review" in data:
        ans.marked_for_review = bool(data["marked_for_review"])
        update_fields.append("marked_for_review")

    if "doubt" in data:
        ans.doubt = bool(data["doubt"])
        update_fields.append("doubt")

    if "notes_md" in data:
        ans.notes_md = str(data["notes_md"])
        update_fields.append("notes_md")

    if not ans.first_seen_at:
        ans.first_seen_at = now
        update_fields.append("first_seen_at")

    has_content = bool(ans.selected_option_ids or ans.numeric_value is not None)
    ans.status = AttemptAnswer.Status.ANSWERED if has_content else AttemptAnswer.Status.SEEN
    ans.answered_at = now if has_content else ans.answered_at
    ans.answer_changes += 1
    ans.client_ts = ts_dt or now
    if ts_dt:
        update_fields.append("client_ts")
    if ans.answered_at:
        update_fields.append("answered_at")

    ans.save()
    session.last_active_at = now
    session.save(update_fields=["last_active_at", "active_seconds", "updated_at"])

    return AnswerSaved(
        session_id=session_id,
        position=ans.position,
        status=ans.status,
        time_spent_ms=ans.time_spent_ms,
        answer_id=ans.id,
    )


def check_answer(
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    position: int | None = None,
    *,
    question_id: uuid.UUID | None = None,
    answer_json: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Feedback:
    """Instant feedback check for a single question."""
    user_id = user_id or kwargs.get("user_id")
    session_id = session_id or kwargs.get("session_id")

    session = Session.objects.filter(id=session_id, user_id=user_id).first()
    if not session:
        raise SessionNotFound("Session not found.")

    if session.status in (Session.Status.SUBMITTED, Session.Status.AUTO_SUBMITTED, Session.Status.ABANDONED):
        raise SessionClosed(f"Session is {session.status}.")
    if _expire_if_overdue(session):
        raise SessionClosed("Time is up. The session was submitted automatically.")

    if session.feedback_policy != Session.FeedbackPolicy.INSTANT:
        raise InstantFeedbackDisabled("Instant check is only available for instant feedback sessions.")

    ans_qs = AttemptAnswer.objects.filter(session_id=session_id, user_id=user_id)
    if position is not None:
        ans = ans_qs.filter(position=position).first()
    elif question_id is not None:
        ans = ans_qs.filter(question_id=question_id).first()
    else:
        raise ValueError("Must provide position or question_id.")

    if not ans:
        raise ValueError("Answer row not found.")

    if answer_json:
        # Save before checking if new answer supplied
        if "selected_option_ids" in answer_json:
            ans.selected_option_ids = [str(x) for x in answer_json["selected_option_ids"]]
        if "numeric_value" in answer_json:
            val = answer_json["numeric_value"]
            ans.numeric_value = Decimal(str(val)) if val is not None else None
            ans.numeric_unit = answer_json.get("numeric_unit")

    # Retrieve gradable question
    gradables = qb_selectors.get_gradables([(ans.question_id, ans.question_version_id)])
    g = gradables.get(ans.question_id)
    if not g:
        raise ValueError("Gradable question not found.")

    snapshot = session.scoring_snapshot
    multi_mode = snapshot.get("multi_mode", "all_or_nothing")

    if g.kind in ("mcq_single", "mcq_multi", "true_false"):
        opt_keys = [OptionKey(id=opt.id, is_correct=opt.is_correct) for opt in g.options]
        sel_uuids = [uuid.UUID(str(oid)) for oid in ans.selected_option_ids]
        grading = grade_choice(
            kind=g.kind,
            selected_option_ids=sel_uuids,
            options=opt_keys,
            marks_max=ans.marks_max,
            negative_max=ans.negative_max,
            multi_mode=multi_mode,
        )
    elif g.kind == "numeric":
        num_key = NumericKey(
            numeric_value=g.answer_key.numeric_value if g.answer_key else Decimal("0"),
            tolerance_abs=g.answer_key.tolerance_abs if g.answer_key else Decimal("0"),
            tolerance_rel=g.answer_key.tolerance_rel if g.answer_key else Decimal("0"),
            accepted_values=g.answer_key.accepted_values if g.answer_key else [],
        )
        grading = grade_numeric(
            student_value=ans.numeric_value,
            key=num_key,
            marks_max=ans.marks_max,
            negative_max=ans.negative_max,
        )
    else:
        # Long-form / practical
        grading = grade_choice("mcq_single", [], [], ans.marks_max, ans.negative_max)

    now = timezone.now()
    ans.result = grading.result
    ans.marks_awarded = grading.marks_awarded
    ans.negative_applied = grading.negative_applied
    ans.status = AttemptAnswer.Status.GRADED
    ans.grading_source = AttemptAnswer.GradingSource.AUTO
    ans.checked_at = now
    ans.save()

    opts_fb = [{"id": opt.id, "is_correct": opt.is_correct, "feedback_md": opt.feedback_md} for opt in g.options]

    return Feedback(
        result=grading.result,
        marks_awarded=grading.marks_awarded,
        negative_applied=grading.negative_applied,
        explanation_md=g.explanation_md,
        options_feedback=opts_fb,
    )


def start_session(
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    **kwargs: Any,
) -> None:
    """
    Starts the clock when the student opens the session, not when she first answers (a timed paper must not give
    free reading time). Idempotent and race-safe: only a session still `created` changes, whoever asks first.
    """
    user_id = user_id or kwargs.get("user_id")
    session_id = session_id or kwargs.get("session_id")
    session = Session.objects.filter(id=session_id, user_id=user_id).first()
    if not session:
        raise SessionNotFound("Session not found.")
    if session.status != Session.Status.CREATED:
        return
    now = timezone.now()
    Session.objects.filter(id=session.id, status=Session.Status.CREATED).update(
        status=Session.Status.IN_PROGRESS,
        started_at=now,
        deadline_at=calculate_deadline(now, session.time_limit_seconds, session.paused_total_seconds),
        last_active_at=now,
        updated_at=now,
    )


def pause_session(
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    **kwargs: Any,
) -> None:
    user_id = user_id or kwargs.get("user_id")
    session_id = session_id or kwargs.get("session_id")
    session = Session.objects.filter(id=session_id, user_id=user_id).first()
    if not session:
        raise SessionNotFound("Session not found.")
    if _expire_if_overdue(session):
        raise SessionClosed("Time is up. The session was submitted automatically.")
    if not pause_allowed(session.mode, session.spec):
        raise PauseNotAllowed("Pausing is not allowed for this session.")
    if session.status == Session.Status.PAUSED:
        return  # a double tap, or a second tab: already where the student wanted it
    now = timezone.now()
    if session.status == Session.Status.CREATED:
        # Never answered, so the clock has not started. Pausing starts it and stops it at once.
        session.status = Session.Status.IN_PROGRESS
        session.started_at = now
        session.deadline_at = calculate_deadline(now, session.time_limit_seconds, session.paused_total_seconds)
    try:
        validate_transition(session.status, Session.Status.PAUSED)
    except Exception as e:
        raise SessionClosed(str(e)) from e
    session.status = Session.Status.PAUSED
    session.paused_at = now
    session.save(update_fields=["status", "started_at", "deadline_at", "paused_at", "updated_at"])


def resume_session(
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    **kwargs: Any,
) -> None:
    user_id = user_id or kwargs.get("user_id")
    session_id = session_id or kwargs.get("session_id")
    session = Session.objects.filter(id=session_id, user_id=user_id).first()
    if not session:
        raise SessionNotFound("Session not found.")
    try:
        validate_transition(session.status, Session.Status.IN_PROGRESS)
    except Exception as e:
        raise SessionClosed(str(e)) from e

    now = timezone.now()
    if session.paused_at:
        delta = int((now - session.paused_at).total_seconds())
        session.paused_total_seconds += delta
        session.deadline_at = calculate_deadline(
            session.started_at, session.time_limit_seconds, session.paused_total_seconds
        )
        session.paused_at = None

    session.status = Session.Status.IN_PROGRESS
    session.save(update_fields=["status", "paused_at", "paused_total_seconds", "deadline_at", "updated_at"])


def submit_session(
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    *,
    auto: bool = False,
    **kwargs: Any,
) -> SessionResult:
    """Submit a session, auto-grade remaining answers, compute stats, and emit event."""
    user_id = user_id or kwargs.get("user_id")
    session_id = session_id or kwargs.get("session_id")
    session = Session.objects.filter(id=session_id, user_id=user_id).first()
    if not session:
        raise SessionNotFound("Session not found.")

    if session.status in (Session.Status.SUBMITTED, Session.Status.AUTO_SUBMITTED):
        # Idempotent return
        return SessionResult(
            session_id=session.id,
            score=session.score or Decimal("0.00"),
            max_score=session.max_score or Decimal("0.00"),
            score_status=session.score_status,
            counts={
                "answered": session.answered_count,
                "correct": session.correct_count,
                "incorrect": session.incorrect_count,
                "partial": session.partial_count,
                "skipped": session.skipped_count,
                "pending": session.pending_count,
            },
            by_chapter=[],
        )

    target_status = Session.Status.AUTO_SUBMITTED if auto else Session.Status.SUBMITTED
    validate_transition(session.status, target_status)

    now = timezone.now()
    answers = list(AttemptAnswer.objects.filter(session_id=session_id, user_id=user_id).order_by("position"))

    # Need gradables for all answers that are not yet graded
    ungraded = [ans for ans in answers if ans.status != AttemptAnswer.Status.GRADED]
    refs = [(ans.question_id, ans.question_version_id) for ans in ungraded]
    gradables = qb_selectors.get_gradables(refs) if refs else {}

    multi_mode = session.scoring_snapshot.get("multi_mode", "all_or_nothing")

    with transaction.atomic():
        total_score = Decimal("0.00")
        total_max_score = Decimal("0.00")
        counts = {"answered": 0, "correct": 0, "incorrect": 0, "partial": 0, "skipped": 0, "pending": 0}
        by_chapter_data: dict[uuid.UUID, dict[str, Any]] = defaultdict(
            lambda: {
                "answered": 0,
                "correct": 0,
                "incorrect": 0,
                "skipped": 0,
                "seconds": 0,
                "marks": Decimal("0.00"),
                "max_marks": Decimal("0.00"),
                "chapter_key": None,
                "subject_id": None,
                "subject_key": None,
            }
        )

        for ans in answers:
            total_max_score += ans.marks_max

            if ans.status != AttemptAnswer.Status.GRADED:
                g = gradables.get(ans.question_id)
                if g and g.kind in ("mcq_single", "mcq_multi", "true_false"):
                    opt_keys = [OptionKey(id=opt.id, is_correct=opt.is_correct) for opt in g.options]
                    sel_uuids = [uuid.UUID(str(oid)) for oid in ans.selected_option_ids]
                    grading = grade_choice(
                        kind=g.kind,
                        selected_option_ids=sel_uuids,
                        options=opt_keys,
                        marks_max=ans.marks_max,
                        negative_max=ans.negative_max,
                        multi_mode=multi_mode,
                    )
                elif g and g.kind == "numeric":
                    num_key = NumericKey(
                        numeric_value=g.answer_key.numeric_value if g.answer_key else Decimal("0"),
                        tolerance_abs=g.answer_key.tolerance_abs if g.answer_key else Decimal("0"),
                        tolerance_rel=g.answer_key.tolerance_rel if g.answer_key else Decimal("0"),
                        accepted_values=g.answer_key.accepted_values if g.answer_key else [],
                    )
                    grading = grade_numeric(
                        student_value=ans.numeric_value,
                        key=num_key,
                        marks_max=ans.marks_max,
                        negative_max=ans.negative_max,
                    )
                else:
                    grading = grade_choice("mcq_single", [], [], ans.marks_max, ans.negative_max)

                ans.result = grading.result
                ans.marks_awarded = grading.marks_awarded
                ans.negative_applied = grading.negative_applied
                ans.status = AttemptAnswer.Status.GRADED
                ans.grading_source = AttemptAnswer.GradingSource.AUTO
                ans.graded_at = now
                ans.save()

            if ans.result == AttemptAnswer.Result.CORRECT:
                counts["correct"] += 1
                counts["answered"] += 1
            elif ans.result == AttemptAnswer.Result.INCORRECT:
                counts["incorrect"] += 1
                counts["answered"] += 1
            elif ans.result == AttemptAnswer.Result.PARTIAL:
                counts["partial"] += 1
                counts["answered"] += 1
            elif ans.result == AttemptAnswer.Result.SKIPPED:
                counts["skipped"] += 1
            else:
                counts["pending"] += 1

            if ans.marks_awarded is not None:
                total_score += ans.marks_awarded

            # By chapter rollup
            if ans.chapter_id:
                ch = by_chapter_data[ans.chapter_id]
                ch["subject_id"] = ans.subject_id
                if ans.result in (
                    AttemptAnswer.Result.CORRECT,
                    AttemptAnswer.Result.INCORRECT,
                    AttemptAnswer.Result.PARTIAL,
                ):
                    ch["answered"] += 1
                if ans.result == AttemptAnswer.Result.CORRECT:
                    ch["correct"] += 1
                elif ans.result == AttemptAnswer.Result.INCORRECT:
                    ch["incorrect"] += 1
                elif ans.result == AttemptAnswer.Result.SKIPPED:
                    ch["skipped"] += 1
                ch["seconds"] += ans.time_spent_ms // 1000
                ch["marks"] += ans.marks_awarded or Decimal("0.00")
                ch["max_marks"] += ans.marks_max

            # Update QuestionState (E-F06-1: records chapter_id!)
            if ans.result in (
                AttemptAnswer.Result.CORRECT,
                AttemptAnswer.Result.INCORRECT,
                AttemptAnswer.Result.PARTIAL,
            ):
                state, _ = QuestionState.objects.get_or_create(
                    user_id=user_id,
                    question_id=ans.question_id,
                    defaults={"chapter_id": ans.chapter_id},
                )
                state.chapter_id = ans.chapter_id
                state.attempts += 1
                if ans.result == AttemptAnswer.Result.CORRECT:
                    state.correct_count += 1
                    state.correct_streak += 1
                    state.box = min(5, state.box + 1)
                else:
                    state.correct_streak = 0
                    state.box = max(0, state.box - 1)
                state.last_result = ans.result
                state.last_answer_session_id = session.id
                state.last_attempt_at = now
                state.last_time_ms = ans.time_spent_ms
                state.save()

        # Update Session
        session.status = target_status
        session.submitted_at = now
        session.score = total_score
        session.max_score = total_max_score
        session.score_status = Session.ScoreStatus.FINAL
        session.answered_count = counts["answered"]
        session.correct_count = counts["correct"]
        session.incorrect_count = counts["incorrect"]
        session.partial_count = counts["partial"]
        session.skipped_count = counts["skipped"]
        session.pending_count = counts["pending"]
        session.save()

        # Update DailyRollup
        for ch_id, ch_dict in by_chapter_data.items():
            rollup, _ = DailyRollup.objects.get_or_create(
                user_id=user_id,
                local_date=session.local_date,
                chapter_id=ch_id,
                kind="all",
            )
            rollup.answered += ch_dict["answered"]
            rollup.correct += ch_dict["correct"]
            rollup.incorrect += ch_dict["incorrect"]
            rollup.skipped += ch_dict["skipped"]
            rollup.time_ms += ch_dict["seconds"] * 1000
            rollup.marks += ch_dict["marks"]
            rollup.marks_max += ch_dict["max_marks"]
            rollup.subject_id = ch_dict["subject_id"]
            rollup.save()

        # Prepare by_chapter payload
        by_chapter_list = [
            {
                "chapter_id": str(ch_id),
                "chapter_key": None,
                "subject_id": str(v["subject_id"]) if v["subject_id"] else None,
                "subject_key": None,
                "answered": v["answered"],
                "correct": v["correct"],
                "incorrect": v["incorrect"],
                "skipped": v["skipped"],
                "seconds": v["seconds"],
                "marks": float(v["marks"]),
                "max_marks": float(v["max_marks"]),
            }
            for ch_id, v in by_chapter_data.items()
        ]

        # Emit practice_session_completed
        emit_domain_event(
            "practice_session_completed",
            {
                "session_id": str(session.id),
                "mode": session.mode,
                "origin_module": session.origin_module,
                "origin_ref": session.origin_ref,
                "completion": "auto_submitted" if auto else "submitted",
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.submitted_at.isoformat() if session.submitted_at else None,
                "active_seconds": session.active_seconds,
                "tz": session.tz,
                "local_date": session.local_date.isoformat(),
                "scoring_profile": session.scoring_profile,
                "rule_verified": session.scoring_snapshot.get("verified", False),
                "score": float(session.score or 0),
                "max_score": float(session.max_score or 0),
                "score_status": session.score_status,
                "counts": counts,
                "by_chapter": by_chapter_list,
                "retake_of_id": str(session.retake_of_id) if session.retake_of_id else None,
            },
            user_id=user_id,
            key=str(session.id),
        )

    return SessionResult(
        session_id=session.id,
        score=session.score,
        max_score=session.max_score,
        score_status=session.score_status,
        counts=counts,
        by_chapter=by_chapter_list,
    )


def retake(
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    scope: Literal["all", "wrong", "unattempted", "flagged"] = "all",
    *,
    client_id: uuid.UUID | None = None,
    **kwargs: Any,
) -> SessionCreated:
    """Create a retake session based on a previous session's items."""
    user_id = user_id or kwargs.get("user_id")
    session_id = session_id or kwargs.get("session_id")
    parent = Session.objects.filter(id=session_id, user_id=user_id).first()
    if not parent:
        raise SessionNotFound("Parent session not found.")

    if not (parent.spec or {}).get("allow_retake", True):
        raise ForbiddenRetake("Retake is not permitted for this session.")

    answers = AttemptAnswer.objects.filter(session_id=session_id, user_id=user_id).order_by("position")
    if scope == "wrong":
        answers = answers.filter(result__in=[AttemptAnswer.Result.INCORRECT, AttemptAnswer.Result.PARTIAL])
    elif scope == "unattempted":
        answers = answers.filter(status=AttemptAnswer.Status.UNSEEN)
    elif scope == "flagged":
        answers = answers.filter(marked_for_review=True)

    items = [
        {
            "question_id": str(ans.question_id),
            "version_id": str(ans.question_version_id),
            "marks": float(ans.marks_max),
            "negative_marks": float(ans.negative_max),
            "section_label": ans.section_label,
        }
        for ans in answers
    ]

    if not items:
        raise PickerEmpty(f"No questions matched retake scope '{scope}'.")

    return create_session_from_items(
        user_id=user_id,
        mode=parent.mode,
        origin_module=parent.origin_module,
        origin_ref=parent.origin_ref,
        items=items,
        time_limit_seconds=parent.time_limit_seconds,
        feedback_policy=parent.feedback_policy,
        scoring_profile=parent.scoring_profile,
        client_id=client_id,
        tz=parent.tz,
        title=f"Retake: {parent.title}" if parent.title else "Retake",
        retake_of_id=parent.id,
    )


def set_mistake_reason(
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    position: int | None = None,
    reason: str = "",
    note: str = "",
    *,
    question_id: uuid.UUID | None = None,
    mistake_reason: str = "",
    **kwargs: Any,
) -> None:
    """Set mistake reason for an answer."""
    user_id = user_id or kwargs.get("user_id")
    session_id = session_id or kwargs.get("session_id")
    actual_reason = mistake_reason or reason

    ans_qs = AttemptAnswer.objects.filter(session_id=session_id, user_id=user_id)
    if position is not None:
        ans = ans_qs.filter(position=position).first()
    elif question_id is not None:
        ans = ans_qs.filter(question_id=question_id).first()
    else:
        raise ValueError("Must provide position or question_id.")

    if not ans:
        raise SessionNotFound("Answer not found.")

    ans.mistake_reason = actual_reason
    ans.save(update_fields=["mistake_reason", "updated_at"])

    # Update QuestionState
    QuestionState.objects.filter(user_id=user_id, question_id=ans.question_id).update(
        last_mistake_reason=actual_reason,
    )


def set_question_state(
    user_id: uuid.UUID | None = None,
    question_id: uuid.UUID | None = None,
    *,
    bookmarked: bool | None = None,
    doubt: bool | None = None,
    note: str | None = None,
    notes: str | None = None,
    **kwargs: Any,
) -> QuestionState:
    """Update personal question flags (bookmark, doubt, note)."""
    user_id = user_id or kwargs.get("user_id")
    question_id = question_id or kwargs.get("question_id")
    actual_note = notes if notes is not None else note

    state, _ = QuestionState.objects.get_or_create(user_id=user_id, question_id=question_id)
    fields = []
    if bookmarked is not None:
        state.bookmarked = bookmarked
        state.bookmarked_at = timezone.now() if bookmarked else None
        fields.extend(["bookmarked", "bookmarked_at"])
    if doubt is not None:
        state.doubt = doubt
        fields.append("doubt")
    if actual_note is not None:
        state.note = actual_note
        fields.append("note")

    if fields:
        fields.append("updated_at")
        state.save(update_fields=fields)
    return state


def delete_all_for_user(user_id: uuid.UUID) -> dict[str, int]:
    """Delete all user practice data for DPDP compliance."""
    with transaction.atomic():
        deleted_subm, _ = Submission.objects.filter(user_id=user_id).delete()
        deleted_ans, _ = AttemptAnswer.objects.filter(user_id=user_id).delete()
        deleted_sess, _ = Session.objects.filter(user_id=user_id).delete()
        deleted_state, _ = QuestionState.objects.filter(user_id=user_id).delete()
        deleted_roll, _ = DailyRollup.objects.filter(user_id=user_id).delete()

    return {
        "submissions_deleted": deleted_subm,
        "answers_deleted": deleted_ans,
        "sessions_deleted": deleted_sess,
        "states_deleted": deleted_state,
        "rollups_deleted": deleted_roll,
    }


def export_for_user(user_id: uuid.UUID) -> dict[str, Any]:
    """Export all user practice data for DPDP compliance."""
    sessions = list(
        Session.objects.filter(user_id=user_id).values(
            "id", "mode", "origin_module", "status", "score", "max_score", "started_at", "submitted_at"
        )
    )
    states = list(
        QuestionState.objects.filter(user_id=user_id).values(
            "question_id", "bookmarked", "doubt", "attempts", "correct_count", "last_result"
        )
    )
    return {
        "sessions": sessions,
        "question_states": states,
    }
