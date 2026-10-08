"""Errors of the recall module. Shared ones come from `core.errors`; nothing is copied per module."""

from core.errors import CodedError, Conflict, FeatureDisabled, QuotaExceeded

__all__ = ["CodedError", "Conflict", "FeatureDisabled", "QuotaExceeded", "RecallFeatureDisabled"]


class RecallFeatureDisabled(FeatureDisabled):
    default_detail = "Recall is not available yet."
