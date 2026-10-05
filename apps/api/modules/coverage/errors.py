"""Domain errors raised by services. Views translate them into the API's standard error shape."""

from rest_framework.exceptions import APIException, NotFound, ValidationError

from core.errors import Conflict, FeatureDisabled


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


class RuleViolation(CoverageError):
    """A business rule refused the write (409). Carries a machine readable `code` and `details` for the web."""

    code = "rule_violation"


class TargetReachedError(RuleViolation):
    code = "target_reached"


class ActivityNotTrackedError(RuleViolation):
    code = "activity_not_tracked"


class ConfidenceLockedError(RuleViolation):
    code = "confidence_locked"


class TargetReached(Conflict):
    default_detail = "This activity is already at its target."
    default_code = "target_reached"


class ActivityNotTracked(Conflict):
    default_detail = "This activity is not tracked."
    default_code = "activity_not_tracked"


class ConfidenceLocked(Conflict):
    default_detail = "Confidence unlocks at 50% coverage."
    default_code = "confidence_locked"


_RULE_EXCEPTIONS = {
    TargetReachedError: TargetReached,
    ActivityNotTrackedError: ActivityNotTracked,
    ConfidenceLockedError: ConfidenceLocked,
}


class CoverageFeatureDisabled(FeatureDisabled):
    """The `syllabus_coverage` flag is off for this student."""

    default_detail = "My Coverage is not available yet."


class TargetsFeatureDisabled(FeatureDisabled):
    """The `study_targets` flag is off for this student: reading targets works, changing them does not yet."""

    default_detail = "Study targets are not available yet."


def to_api_exception(exc: CoverageError) -> APIException:
    api_class = _RULE_EXCEPTIONS.get(type(exc))
    if api_class:
        return api_class(exc.message)
    if isinstance(exc, NotFoundError):
        return NotFound(exc.message)
    if isinstance(exc, ConflictError):
        return Conflict(exc.message)
    return ValidationError(exc.details or {"detail": exc.message})
