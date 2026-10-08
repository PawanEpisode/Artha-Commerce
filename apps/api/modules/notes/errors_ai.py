"""Errors of the R3 AI features (flag `notes_ai`). Codes are what the web branches on."""

from rest_framework import status

from core.errors import CodedError, Conflict


class AiUnavailable(CodedError):
    """503 `ai_unavailable`: this deployment is not set up for AI (key, data tier, approved wording, kill switch, budget set)."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "AI help is not available yet."
    default_code = "ai_unavailable"


class AiBudgetExhausted(CodedError):
    """503 `ai_budget_exhausted`: today's shared AI budget is spent. Nothing was charged."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "AI help is busy for today. Try again tomorrow."
    default_code = "ai_budget_exhausted"


class AiNotConsented(CodedError):
    """403 `ai_not_consented`, details `{version}`: the student has not agreed to the current consent text."""

    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Agree to the AI notice first."
    default_code = "ai_not_consented"


class ConsentVersionMismatch(Conflict):
    default_detail = "The AI notice changed. Read it again."
    default_code = "consent_version_mismatch"


class NotEnoughMaterial(CodedError):
    """422 `not_enough_material`, details `{items, chars, min_items, min_chars}`."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "There is not enough in this chapter yet to summarise."
    default_code = "not_enough_material"


class DraftNotReady(Conflict):
    default_detail = "This summary is not ready to accept."
    default_code = "not_ready"


class NotCancellable(Conflict):
    default_detail = "This request has already started."
    default_code = "not_cancellable"
