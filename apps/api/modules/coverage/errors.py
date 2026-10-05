"""Domain errors raised by services. Views translate them into the API's standard error shape."""

from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError


class CoverageError(Exception):
    code = "error"

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(CoverageError):
    code = "not_found"


class ConflictError(CoverageError):
    code = "conflict"


class InvalidInput(CoverageError):
    code = "invalid"


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"


class FeatureDisabled(PermissionDenied):
    """The `syllabus_coverage` flag is off for this student. The web shows its own "not available yet" screen."""

    default_detail = "My Coverage is not available yet."
    default_code = "feature_disabled"


def to_api_exception(exc: CoverageError) -> APIException:
    if isinstance(exc, NotFoundError):
        return NotFound(exc.message)
    if isinstance(exc, ConflictError):
        return Conflict(exc.message)
    return ValidationError(exc.details or {"detail": exc.message})
