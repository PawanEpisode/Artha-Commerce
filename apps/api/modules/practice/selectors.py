"""
Practice Engine read selectors (F-06 ERD 3.2, E-F06-1).
"""

from __future__ import annotations

import base64
import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, Max, Q
from django.utils import timezone

from modules.questionbank import selectors as qb_selectors

from .domain.session import shuffle_options
from .models import AttemptAnswer, QuestionState, Session


@dataclass
class Page[T]:
    items: list[T]
    next_cursor: str | None = None
    total: int | None = None


@dataclass
class SessionItemView:
    position: int
    question_id: uuid.UUID
    kind: str
    stem_md: str
    options: list[dict[str, Any]]
    marks_max: Decimal
    negative_max: Decimal
    status: str
    selected_option_ids: list[str]
    numeric_value: Decimal | None
    numeric_unit: str | None
    time_spent_ms: int
    marked_for_review: bool
    doubt: bool
    confidence: int | None
    result: str | None = None
    marks_awarded: Decimal | None = None
    negative_applied: Decimal = Decimal("0.00")
    explanation_md: str | None = None
    feedback: str | None = None


@dataclass
class SessionView:
    id: uuid.UUID
    mode: str
    title: str
    status: str
    feedback_policy: str
    scoring_profile: str
    question_count: int
    total_marks: Decimal
    time_limit_seconds: int | None
    deadline_at: str | None
    score: Decimal | None
    max_score: Decimal | None
    score_status: str
    items: list[SessionItemView]


@dataclass
class SessionRow:
    id: uuid.UUID
    mode: str
    title: str
    status: str
    question_count: int
    score: Decimal | None
    max_score: Decimal | None
    score_status: str
    submitted_at: str | None
    created_at: str


@dataclass
class ChapterProgress:
    attempted: int
    correct_last: int
    wrong_last: int
    bookmarked: int
    due: int
    avg_time_ms: int | None
    last_attempt_at: str | None


@dataclass
class MistakeRow:
    question_id: uuid.UUID
    chapter_id: uuid.UUID | None
    attempts: int
    last_result: str | None
    last_attempt_at: str | None
    mistake_reason: str | None


@dataclass
class BookmarkRow:
    question_id: uuid.UUID
    chapter_id: uuid.UUID | None
    bookmarked_at: str | None
    note: str


def get_session(user_id: uuid.UUID, session_id: uuid.UUID) -> SessionView:
    """
    Retrieve session and its items.
    Enforces ZERO ANSWER LEAKAGE: When the session is not yet submitted,
    answer keys, correctness, and explanations are NEVER returned.
    """
    session = Session.objects.filter(id=session_id, user_id=user_id).first()
    if not session:
        raise ValueError("Session not found.")

    is_submitted = session.status in (Session.Status.SUBMITTED, Session.Status.AUTO_SUBMITTED)
    answers = list(AttemptAnswer.objects.filter(session_id=session_id, user_id=user_id).order_by("position"))

    # Fetch playable or review questions
    items: list[SessionItemView] = []
    for ans in answers:
        if is_submitted:
            rev_q = qb_selectors.get_review_view(ans.question_id, ans.question_version_id)
            # Full review data
            shuffled_opts = shuffle_options(
                [
                    {
                        "id": str(opt["id"] if isinstance(opt, dict) else opt.id),
                        "body_md": opt["body_md"] if isinstance(opt, dict) else opt.body_md,
                        "is_correct": opt["is_correct"] if isinstance(opt, dict) else opt.is_correct,
                        "feedback_md": opt["feedback_md"] if isinstance(opt, dict) else opt.feedback_md,
                        "pinned": opt["pinned"] if isinstance(opt, dict) else opt.pinned,
                    }
                    for opt in rev_q.options
                ],
                seed=session.shuffle_seed,
                position=ans.position,
            )
            item_view = SessionItemView(
                position=ans.position,
                question_id=ans.question_id,
                kind=ans.kind,
                stem_md=rev_q.stem_md,
                options=shuffled_opts,
                marks_max=ans.marks_max,
                negative_max=ans.negative_max,
                status=ans.status,
                selected_option_ids=[str(x) for x in ans.selected_option_ids],
                numeric_value=ans.numeric_value,
                numeric_unit=ans.numeric_unit,
                time_spent_ms=ans.time_spent_ms,
                marked_for_review=ans.marked_for_review,
                doubt=ans.doubt,
                confidence=ans.confidence,
                result=ans.result,
                marks_awarded=ans.marks_awarded,
                negative_applied=ans.negative_applied,
                explanation_md=rev_q.explanation_md,
            )
        else:
            # PLAYABLE: NO KEYS, NO EXPLANATIONS
            playable = qb_selectors.get_playable(ans.question_id, version_id=ans.question_version_id)
            shuffled_opts = shuffle_options(
                [
                    {
                        "id": str(opt.id),
                        "body_md": opt.body_md,
                        "pinned": opt.pinned,
                    }
                    for opt in playable.options
                ],
                seed=session.shuffle_seed,
                position=ans.position,
            )
            # If instant check feedback was already recorded, show only its result
            item_view = SessionItemView(
                position=ans.position,
                question_id=ans.question_id,
                kind=ans.kind,
                stem_md=playable.stem_md,
                options=shuffled_opts,
                marks_max=ans.marks_max,
                negative_max=ans.negative_max,
                status=ans.status,
                selected_option_ids=[str(x) for x in ans.selected_option_ids],
                numeric_value=ans.numeric_value,
                numeric_unit=ans.numeric_unit,
                time_spent_ms=ans.time_spent_ms,
                marked_for_review=ans.marked_for_review,
                doubt=ans.doubt,
                confidence=ans.confidence,
                result=ans.result if ans.status == AttemptAnswer.Status.GRADED else None,
                marks_awarded=ans.marks_awarded if ans.status == AttemptAnswer.Status.GRADED else None,
            )

        items.append(item_view)

    return SessionView(
        id=session.id,
        mode=session.mode,
        title=session.title,
        status=session.status,
        feedback_policy=session.feedback_policy,
        scoring_profile=session.scoring_profile,
        question_count=session.question_count,
        total_marks=session.total_marks,
        time_limit_seconds=session.time_limit_seconds,
        deadline_at=session.deadline_at.isoformat() if session.deadline_at else None,
        score=session.score,
        max_score=session.max_score,
        score_status=session.score_status,
        items=items,
    )


def list_sessions(
    user_id: uuid.UUID,
    *,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> Page[SessionRow]:
    """Keyset-paginated list of user sessions."""
    qs = Session.objects.filter(user_id=user_id)
    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("-created_at", "-id")

    if cursor:
        try:
            raw = base64.urlsafe_b64decode(cursor.encode()).decode()
            c_dt_str, c_id_str = raw.split("|", 1)
            c_dt = timezone.datetime.fromisoformat(c_dt_str)
            c_id = uuid.UUID(c_id_str)
            qs = qs.filter(Q(created_at__lt=c_dt) | Q(created_at=c_dt, id__lt=c_id))
        except Exception:
            pass

    records = list(qs[: limit + 1])
    has_next = len(records) > limit
    page_records = records[:limit]

    items = [
        SessionRow(
            id=s.id,
            mode=s.mode,
            title=s.title,
            status=s.status,
            question_count=s.question_count,
            score=s.score,
            max_score=s.max_score,
            score_status=s.score_status,
            submitted_at=s.submitted_at.isoformat() if s.submitted_at else None,
            created_at=s.created_at.isoformat(),
        )
        for s in page_records
    ]

    next_cursor = None
    if has_next and page_records:
        last = page_records[-1]
        raw_cur = f"{last.created_at}|{last.id}"
        next_cursor = base64.urlsafe_b64encode(raw_cur.encode()).decode()

    return Page(items=items, next_cursor=next_cursor)


def progress_by_chapter(user_id: uuid.UUID, chapter_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, ChapterProgress]:
    """
    E-F06-1: Per-chapter practice progress without scanning answers or cross-module joins.
    """
    now = timezone.now()
    qs = QuestionState.objects.filter(user_id=user_id, chapter_id__in=chapter_ids)

    # Group by chapter_id
    grouped = qs.values("chapter_id").annotate(
        attempted=Count("id", filter=Q(attempts__gt=0)),
        correct_last=Count("id", filter=Q(last_result="correct")),
        wrong_last=Count("id", filter=Q(last_result__in=["incorrect", "partial"])),
        bookmarked=Count("id", filter=Q(bookmarked=True)),
        due=Count("id", filter=Q(next_review_at__isnull=False, next_review_at__lte=now)),
        avg_time=Avg("avg_time_ms"),
        last_attempt=Max("last_attempt_at"),
    )

    result: dict[uuid.UUID, ChapterProgress] = {}
    for row in grouped:
        ch_id = row["chapter_id"]
        result[ch_id] = ChapterProgress(
            attempted=row["attempted"],
            correct_last=row["correct_last"],
            wrong_last=row["wrong_last"],
            bookmarked=row["bookmarked"],
            due=row["due"],
            avg_time_ms=int(row["avg_time"]) if row["avg_time"] is not None else None,
            last_attempt_at=row["last_attempt"].isoformat() if row["last_attempt"] else None,
        )

    # Empty entries for missing chapters
    for ch_id in chapter_ids:
        if ch_id not in result:
            result[ch_id] = ChapterProgress(
                attempted=0,
                correct_last=0,
                wrong_last=0,
                bookmarked=0,
                due=0,
                avg_time_ms=None,
                last_attempt_at=None,
            )

    return result


def get_question_states(
    user_id: uuid.UUID,
    question_ids: Sequence[uuid.UUID],
) -> list[QuestionState]:
    """Returns QuestionState records for a student across specific questions."""
    return list(QuestionState.objects.filter(user_id=user_id, question_id__in=question_ids))


def state_stamp(user_id: uuid.UUID) -> str:
    """E-F06-1: State stamp for HTTP conditional headers and cache invalidation."""
    agg = QuestionState.objects.filter(user_id=user_id).aggregate(
        cnt=Count("id"),
        latest=Max("updated_at"),
    )
    seed = f"{user_id}:{agg['cnt']}:{agg['latest']}"
    return hashlib.md5(seed.encode()).hexdigest()


def list_mistakes(
    user_id: uuid.UUID,
    *,
    chapter_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> Page[MistakeRow]:
    """List student's mistake questions."""
    qs = QuestionState.objects.filter(user_id=user_id, last_result__in=["incorrect", "partial"])
    if chapter_id:
        qs = qs.filter(chapter_id=chapter_id)

    qs = qs.order_by("-last_attempt_at", "-question_id")

    records = list(qs[: limit + 1])
    has_next = len(records) > limit
    page_records = records[:limit]

    items = [
        MistakeRow(
            question_id=s.question_id,
            chapter_id=s.chapter_id,
            attempts=s.attempts,
            last_result=s.last_result,
            last_attempt_at=s.last_attempt_at.isoformat() if s.last_attempt_at else None,
            mistake_reason=s.last_mistake_reason,
        )
        for s in page_records
    ]

    next_cursor = None
    if has_next and page_records:
        last = page_records[-1]
        raw_cur = f"{last.last_attempt_at.isoformat() if last.last_attempt_at else ''}|{last.question_id}"
        next_cursor = base64.urlsafe_b64encode(raw_cur.encode()).decode()

    return Page(items=items, next_cursor=next_cursor)


def list_bookmarks(
    user_id: uuid.UUID,
    *,
    chapter_id: uuid.UUID | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> Page[BookmarkRow]:
    """List student's bookmarked questions."""
    qs = QuestionState.objects.filter(user_id=user_id, bookmarked=True)
    if chapter_id:
        qs = qs.filter(chapter_id=chapter_id)
    qs = qs.order_by("-bookmarked_at", "-question_id")

    records = list(qs[: limit + 1])
    has_next = len(records) > limit
    page_records = records[:limit]

    items = [
        BookmarkRow(
            question_id=s.question_id,
            chapter_id=s.chapter_id,
            bookmarked_at=s.bookmarked_at.isoformat() if s.bookmarked_at else None,
            note=s.note,
        )
        for s in page_records
    ]

    next_cursor = None
    if has_next and page_records:
        last = page_records[-1]
        raw_cur = f"{last.bookmarked_at.isoformat() if last.bookmarked_at else ''}|{last.question_id}"
        next_cursor = base64.urlsafe_b64encode(raw_cur.encode()).decode()

    return Page(items=items, next_cursor=next_cursor)
