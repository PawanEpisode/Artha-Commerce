"""
Errors for F-08 Mock Tests module.
"""

from __future__ import annotations

import uuid
from typing import Any
from rest_framework import status
from rest_framework.exceptions import APIException


class MocktestError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "mocktest_error"
    default_detail = "An error occurred in mock tests."


class FeatureDisabled(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "feature_disabled"
    default_detail = "Mock tests feature is currently disabled."


class ExamInProgress(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "exam_in_progress"

    def __init__(self, attempt_id: uuid.UUID | str):
        super().__init__(
            detail={
                "message": "Another strict exam is already in progress.",
                "attempt_id": str(attempt_id),
            },
            code=self.default_code,
        )


class TimerRunning(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "timer_running"
    default_detail = "A focus timer or stopwatch is currently running. Stop it before starting an exam."


class PaperNotAvailable(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "paper_not_available"
    default_detail = "The requested paper is not available to attempt."


class InvalidBlueprint(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "invalid_blueprint"

    def __init__(self, problems: list[str] | list[dict[str, Any]]):
        super().__init__(detail={"problems": problems}, code=self.default_code)


class ChecksFailed(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "checks_failed"

    def __init__(self, problems: list[str]):
        super().__init__(detail={"problems": problems}, code=self.default_code)


class NotEnoughQuestions(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "not_enough_questions"

    def __init__(self, message: str, shortfalls: list[dict[str, Any]] | None = None):
        detail: dict[str, Any] = {"message": message}
        if shortfalls:
            detail["shortfalls"] = shortfalls
        super().__init__(detail=detail, code=self.default_code)


class LeaseHeld(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "lease_held"

    def __init__(self, holder_label: str = ""):
        super().__init__(
            detail={"message": "Exam is active in another tab.", "holder": holder_label},
            code=self.default_code,
        )


class LeaseLost(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "lease_lost"

    def __init__(self, holder_label: str = ""):
        super().__init__(
            detail={"message": "Exam lease was taken over by another tab.", "holder": holder_label},
            code=self.default_code,
        )


class ReadingPhase(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "reading_phase"
    default_detail = "Answers are locked during reading time."


class SectionClosed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "section_closed"
    default_detail = "This section is closed for writes."


class ChoiceLimitReached(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "choice_limit_reached"
    default_detail = "You have already answered the maximum allowed questions for this choice group."


class AttemptClosed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "attempt_closed"
    default_detail = "The exam attempt has ended."


class PauseLimitReached(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "pause_limit_reached"
    default_detail = "Maximum pauses reached for this relaxed attempt."


class ReviewLocked(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "review_locked"
    default_detail = "Review is only available after submitting the exam."
