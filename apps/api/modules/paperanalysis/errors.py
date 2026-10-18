"""
Error classes for F-11 Paper Analysis.
"""

from rest_framework import status

from core.errors import CodedError


class PaperConflict(CodedError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Another editor modified this paper. Please reload."
    default_code = "paper_conflict"


class PaperExists(CodedError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "A paper for this sitting, kind, and series already exists."
    default_code = "paper_exists"


class PaperNotReady(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "All question marks must be confirmed before publishing (or at least 95% with an exception note)."
    default_code = "paper_not_ready"


class AllocationSumMismatch(CodedError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Sum of allocated marks must exactly equal the question marks."
    default_code = "allocation_sum_mismatch"


class AiBudgetExceeded(CodedError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "AI suggestion budget for today has been exceeded."
    default_code = "ai_budget_exceeded"


class SnapshotStale(CodedError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Recommendations snapshot is stale. Please preview again."
    default_code = "snapshot_stale"
