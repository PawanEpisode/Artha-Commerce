"""
Domain exceptions for Progression and Level Transition (F-18).
"""

from rest_framework.exceptions import APIException, NotFound, ValidationError

from core.errors import Conflict


class ProgressionError(Exception):
    code = "error"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(ProgressionError):
    code = "not_found"


class ConflictError(ProgressionError):
    code = "conflict"


class InvalidInput(ProgressionError):
    code = "invalid"


class RollbackExpiredError(ProgressionError):
    code = "rollback_expired"


class RollbackExpired(Conflict):
    default_detail = "Transitions can only be rolled back within 48 hours of creation."
    default_code = "rollback_expired"


_CUSTOM_EXCEPTIONS = {
    RollbackExpiredError: RollbackExpired,
}


def to_api_exception(exc: ProgressionError) -> APIException:
    api_class = _CUSTOM_EXCEPTIONS.get(type(exc))
    if api_class:
        return api_class(exc.message)
    if isinstance(exc, NotFoundError):
        return NotFound(exc.message)
    if isinstance(exc, ConflictError):
        return Conflict(exc.message)
    return ValidationError(exc.details or {"detail": exc.message})
