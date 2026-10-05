"""Domain errors raised by services. Views translate them into the API's standard error shape."""

from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError


class TrackingError(Exception):
    code = "error"

    def __init__(self, message: str, details: dict | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code


class NotFoundError(TrackingError):
    code = "not_found"


class ConflictError(TrackingError):
    """The request is valid but clashes with current state (live timer, stale version, overlap)."""

    code = "conflict"


class InvalidInput(TrackingError):
    code = "invalid"


class GoneError(TrackingError):
    code = "gone"


class Conflict(APIException):
    """A 409 whose body keeps structured details (live timer, latest stopwatch) as real JSON, not strings."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"

    def __init__(self, detail=None, code=None):
        self.detail = detail if detail is not None else self.default_detail
        if code:
            self.default_code = code


class Gone(APIException):
    status_code = status.HTTP_410_GONE
    default_detail = "That is no longer available."
    default_code = "gone"


class FeatureDisabled(PermissionDenied):
    """The `time_tracker` flag is off for this student. The web shows its own "not available yet" screen."""

    default_detail = "The time tracker is not available yet."
    default_code = "feature_disabled"


def to_api_exception(exc: TrackingError) -> APIException:
    if isinstance(exc, NotFoundError):
        return NotFound(exc.message)
    if isinstance(exc, ConflictError):
        # `default_code` is what the shared handler reports, so each conflict keeps its own machine-readable code.
        error = Conflict({"detail": exc.message, **(exc.details or {})})
        error.default_code = exc.code
        return error
    if isinstance(exc, GoneError):
        return Gone(exc.message)
    error = ValidationError(
        {"detail": exc.message, **(exc.details or {})}
        if exc.code != "invalid"
        else exc.details or {"detail": exc.message}
    )
    error.default_code = exc.code
    return error
