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


class TaskNotFound(CodedError):
    """Also what another student's task id gets: nothing tells the two cases apart."""

    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "That task does not exist."
    default_code = "task_not_found"


class InvalidTransitionError(CodedError):
    """422 with the actions the task allows from where it is, so the web can repair its menu."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "That is not possible for this task right now."
    default_code = "invalid_transition"


class StateConflict(CodedError):
    """409 carrying the current task: another device changed it first (done always wins, a stale skip never beats it)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "This task was changed somewhere else."
    default_code = "state_conflict"


class PlanChanged(CodedError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Your plan changed. Reload it and try again."
    default_code = "plan_changed"


class UndoExpiredError(CodedError):
    status_code = status.HTTP_410_GONE
    default_detail = "The undo window has passed."
    default_code = "undo_expired"


class NoAlternative(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "There is nothing else to swap this for today."
    default_code = "no_alternative"


class ProviderTaskReadOnly(CodedError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "Suggested tasks cannot be edited or deleted. Skip or snooze them instead."
    default_code = "provider_task_readonly"


class InvalidScope(CodedError):
    """A paper or chapter that is not in the student's course."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Pick a paper and chapter from your course."
    default_code = "invalid_scope"
