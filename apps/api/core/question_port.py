"""
The question port (F-15 FR-F15-17): how recall asks the question bank (F-06) for the source of a question she got wrong, without
importing it. F-06 does not exist yet. Until it registers a provider `get_question_provider()` answers None and the "Make a card
from this question" call answers 503 `question_source_unavailable`. Same shape as `core.recall_port` and `core.today_port`: the
dependency points at `core`, never from one feature module to another.

A provider answers `source_for(user_id, question_id, version_id)` with a `QuestionSource` or None (no such question, or this
student may not see it). The source is what the question bank itself holds: the explanation text and the reference labels of the
source it cites. Recall never asks a model and never invents a source; a card is only made from what the provider returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from rest_framework import status

from core.errors import CodedError


@dataclass(frozen=True)
class QuestionSource:
    """
    What the question bank says about one version of one question.

    `reference_labels` are the readable names of the provisions it cites ("Section 17(5), CGST Act"); `reference_keys` are their
    stable keys (`cgst:17(5)`), used to match amendments. `chapter_id` and `topic_id` are where the question sits in the syllabus.
    `explanation_md` is the bank's own explanation, already sanitised by F-06.
    """

    question_id: UUID
    version_id: UUID
    explanation_md: str
    reference_labels: tuple[str, ...] = ()
    reference_keys: tuple[str, ...] = ()
    chapter_id: UUID | None = None
    topic_id: UUID | None = None
    source_label: str = ""  # e.g. the module or paper the explanation is drawn from
    extra: dict[str, Any] = field(default_factory=dict)


class QuestionSourceUnavailable(CodedError):
    """No question bank is registered (or it is off for this student): 503, so a caller that does not catch it still answers well."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Cards from questions are not available yet."
    default_code = "question_source_unavailable"


@runtime_checkable
class QuestionProvider(Protocol):
    def source_for(self, user_id: Any, question_id: UUID, version_id: UUID) -> QuestionSource | None: ...


class NullQuestionProvider:
    """The explicit "no question bank" state. Treated like an absent provider."""

    def source_for(self, user_id: Any, question_id: UUID, version_id: UUID) -> QuestionSource | None:
        raise QuestionSourceUnavailable


_provider: QuestionProvider | None = None


def register_question_provider(provider: QuestionProvider | None) -> None:
    """Install the provider (None removes it; tests use that to reset). The last registration wins."""
    global _provider
    _provider = provider


def get_question_provider() -> QuestionProvider | None:
    """The registered provider, or None when the question bank is absent (nothing registered, or the Null provider)."""
    return None if isinstance(_provider, NullQuestionProvider) else _provider
