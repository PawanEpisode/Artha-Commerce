"""Shared API errors. The exception class carries the machine-readable `code` the web branches on (see `core.exceptions`)."""

from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied


class CodedError(APIException):
    """
    An error with its own `default_code` and optional `extra` details (numbers stay numbers; DRF would stringify a
    `detail` dict). Subclass it and set `status_code`, `default_code` and `default_detail`.
    """

    def __init__(self, detail: str | None = None, *, extra: dict | None = None):
        super().__init__(detail)
        self.extra = extra


class Conflict(CodedError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"


class FeatureDisabled(PermissionDenied):
    """A feature flag is off for this student. The web shows its own "not available yet" state."""

    default_detail = "This feature is not available yet."
    default_code = "feature_disabled"


class QuotaExceeded(CodedError):
    """429 with `extra` `{kind, used, limit, plan}`. Quotas are database facts; a throttle is only politeness."""

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "You have reached a limit of your plan."
    default_code = "quota_exceeded"
