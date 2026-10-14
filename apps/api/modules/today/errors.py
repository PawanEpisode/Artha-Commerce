"""Errors Today raises. Each carries the machine-readable `code` the web branches on (see `core.exceptions`)."""

from rest_framework import status

from core.errors import CodedError


class PlanNotGenerated(CodedError):
    """`GET plan/` never generates. The web answers with `POST open/`."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "There is no plan for this day yet."
    default_code = "plan_not_generated"


class InvalidDate(CodedError):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "That date cannot be used here."
    default_code = "invalid_date"
