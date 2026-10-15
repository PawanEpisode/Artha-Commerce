"""
Ports integration for Practice Engine.

Registers providers for:
1. `core.question_port` (Recall card-from-question)
2. `core.suggestion_source_port` ('wrong_answers' source for Recall AI suggestions)
3. `core.today_port` (Today practice tasks)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from core import question_port, suggestion_source_port, today_port
from core.feature_flags import flag_enabled
from core.question_port import QuestionSource
from core.suggestion_source_port import SourcePiece

logger = logging.getLogger(__name__)

FLAG_NAME = "question_bank"


class QuestionProviderImpl:
    """Answers Recall's question source lookup from QuestionBank versions."""

    def source_for(self, user_id: Any, question_id: UUID, version_id: UUID) -> QuestionSource | None:
        try:
            if not flag_enabled(FLAG_NAME, user_id, strict=True):
                return None
        except Exception:
            return None

        from modules.questionbank.models import QuestionVersion

        try:
            qv = QuestionVersion.objects.select_related("question").get(
                id=version_id,
                question_id=question_id,
            )
        except QuestionVersion.DoesNotExist:
            return None

        return QuestionSource(
            question_id=question_id,
            version_id=version_id,
            explanation_md=qv.explanation_md or "",
            reference_labels=tuple(qv.reference_labels or ()),
            chapter_id=qv.question.primary_chapter_id,
            topic_id=qv.question.primary_topic_id,
            source_label=qv.explanation_source or "",
            extra={},
        )


class WrongAnswersSuggestionSource:
    """Answers Recall's AI suggestion source with mistake explanations for a chapter."""

    def texts_for(self, user_id: Any, chapter_id: UUID, *, limit: int) -> list[SourcePiece]:
        try:
            if not flag_enabled(FLAG_NAME, user_id, strict=True):
                return []
        except Exception:
            return []

        from modules.practice.models import QuestionState
        from modules.questionbank.models import QuestionVersion

        # Select questions the student has missed or has wrong attempts in this chapter
        states = list(
            QuestionState.objects.filter(
                user_id=user_id,
                chapter_id=chapter_id,
            )
            .exclude(box__gte=4)
            .order_by("-last_attempt_at", "question_id")[:limit]
        )

        if not states:
            states = list(
                QuestionState.objects.filter(
                    user_id=user_id,
                    chapter_id=chapter_id,
                    last_result="incorrect",
                ).order_by("-last_attempt_at", "question_id")[:limit]
            )

        if not states:
            return []

        q_ids = [s.question_id for s in states]
        # Fetch live versions for these questions
        versions_by_qid: dict[UUID, QuestionVersion] = {}
        versions = QuestionVersion.objects.filter(
            question_id__in=q_ids,
            state=QuestionVersion.State.LIVE,
        ).order_by("question_id", "-version_no")
        for v in versions:
            if v.question_id not in versions_by_qid:
                versions_by_qid[v.question_id] = v

        out: list[SourcePiece] = []
        for s in states:
            v = versions_by_qid.get(s.question_id)
            if not v:
                continue
            text = (v.explanation_md or v.stem_text or v.stem_md or "").strip()
            if s.notes:
                text = f"{text}\nMy notes: {s.notes}".strip()
            if text:
                out.append(
                    SourcePiece(
                        ref=f"question:{s.question_id}",
                        label="Question mistake",
                        text=text[:1500],
                    )
                )

        return out[:limit]


@dataclass(frozen=True)
class PracticeTodayTask:
    kind: str = "practice"
    title: str = "Practice questions"
    count: int = 0
    est_minutes: int = 15
    action_url: str = "/practice"


@dataclass(frozen=True)
class PracticeTaskResult:
    key: str = "practice"
    tasks: list[Any] = field(default_factory=list)


def provide_today(user_id: Any, *, now: datetime) -> PracticeTaskResult | None:
    """Answers Today with active practice sessions or due reviews."""
    try:
        if not flag_enabled(FLAG_NAME, user_id, strict=True):
            return None
    except Exception:
        return None

    from modules.practice.models import Session

    try:
        in_progress_count = Session.objects.filter(
            user_id=user_id,
            status__in=[Session.Status.CREATED, Session.Status.IN_PROGRESS, Session.Status.PAUSED],
        ).count()

        tasks = []
        if in_progress_count > 0:
            tasks.append(
                PracticeTodayTask(
                    kind="practice_resume",
                    title="Resume practice session",
                    count=in_progress_count,
                    est_minutes=15,
                    action_url="/practice",
                )
            )
        return PracticeTaskResult(key="practice", tasks=tasks)
    except Exception:
        logger.warning("Practice Today provider failed for user %s", user_id, exc_info=True)
        return None


def register_ports() -> None:
    """Registers all Practice providers to core ports."""
    question_port.register_question_provider(QuestionProviderImpl())
    suggestion_source_port.register_suggestion_source("wrong_answers", WrongAnswersSuggestionSource())
    today_port.register_task_provider("practice", provide_today)
